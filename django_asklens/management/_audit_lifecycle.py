"""Internal helpers for bounded database audit lifecycle commands."""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import CommandError, CommandParser
from django.db import DatabaseError, connections, transaction
from django.db.models import Q, QuerySet
from django.db.utils import ConnectionDoesNotExist
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from django_asklens.models import SemanticQueryRun

DEFAULT_BATCH_SIZE = 1_000
MAX_BATCH_SIZE = 10_000
_BEFORE_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?"
    r"(?:Z|[+-][0-9]{2}:[0-9]{2})\Z"
)
_BEFORE_ERROR = (
    "--before must be an uppercase, offset-aware RFC 3339 timestamp "
    "earlier than the current time."
)
_BATCH_SIZE_ERROR = "--batch-size must be an integer from 1 through 10000."
_TABLE_ERROR = "The AskLens audit table is unavailable on the selected database."


def _current_time() -> datetime:
    """Return the current aware time through a deterministic test seam."""

    return datetime.now(tz=UTC)


def parse_before(value: object) -> datetime:
    """Parse the command's strict aware RFC 3339 cutoff."""

    if not isinstance(value, str) or _BEFORE_PATTERN.fullmatch(value) is None:
        raise CommandError(_BEFORE_ERROR)

    try:
        parsed = parse_datetime(value)
    except ValueError:
        raise CommandError(_BEFORE_ERROR) from None
    if parsed is None or timezone.is_naive(parsed):
        raise CommandError(_BEFORE_ERROR)

    now = _current_time()
    if timezone.is_naive(now):
        raise RuntimeError("The audit lifecycle clock must be timezone-aware.")
    if parsed >= now:
        raise CommandError(_BEFORE_ERROR)
    return parsed


def canonical_utc(value: datetime) -> str:
    """Serialize one aware cutoff as a compact canonical UTC timestamp."""

    utc_value = value.astimezone(UTC)
    base = utc_value.strftime("%Y-%m-%dT%H:%M:%S")
    if utc_value.microsecond:
        fraction = f"{utc_value.microsecond:06d}".rstrip("0")
        return f"{base}.{fraction}Z"
    return f"{base}Z"


def validate_batch_size(value: object) -> int:
    """Return a bounded positive command batch size."""

    if isinstance(value, bool):
        raise CommandError(_BATCH_SIZE_ERROR)
    if isinstance(value, int):
        batch_size = value
    elif isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value):
        batch_size = int(value)
    else:
        raise CommandError(_BATCH_SIZE_ERROR)
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise CommandError(_BATCH_SIZE_ERROR)
    return batch_size


def _batch_size_argument(value: str) -> int:
    """Adapt shared batch validation to argparse's safe error flow."""

    try:
        return validate_batch_size(value)
    except CommandError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def add_lifecycle_arguments(
    parser: CommandParser,
    *,
    execute_help: str,
) -> None:
    """Add the exact shared preview/execute lifecycle command options."""

    parser.add_argument(
        "--before",
        required=True,
        metavar="RFC3339",
        help="Strict aware RFC 3339 cutoff; matching rows are older than it.",
    )
    parser.add_argument(
        "--database",
        default="default",
        help="Django database alias containing built-in AskLens audit rows.",
    )
    parser.add_argument(
        "--batch-size",
        default=DEFAULT_BATCH_SIZE,
        type=_batch_size_argument,
        help="Rows per short transaction (1 through 10000; default 1000).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=execute_help,
    )


def ensure_audit_table(alias: object) -> str:
    """Validate a configured alias containing the built-in audit table."""

    if not isinstance(alias, str) or not alias:
        raise CommandError("Select a configured database alias.")
    try:
        connection = connections[alias]
    except ConnectionDoesNotExist:
        raise CommandError("Select a configured database alias.") from None

    try:
        tables = connection.introspection.table_names()
    except (DatabaseError, ImproperlyConfigured):
        raise CommandError(_TABLE_ERROR) from None
    if SemanticQueryRun._meta.db_table not in tables:
        raise CommandError(_TABLE_ERROR)
    return alias


def redaction_queryset(*, alias: str, before: datetime) -> QuerySet[SemanticQueryRun]:
    """Build the selected-alias queryset for rows retaining audit content."""

    return (
        SemanticQueryRun.objects.using(alias)
        .filter(created_at__lt=before)
        .filter(~Q(question="") | ~Q(plan={}))
    )


def redact_in_batches(*, alias: str, before: datetime, batch_size: int) -> int:
    """Redact eligible rows in short, deterministic primary-key batches."""

    redacted = 0
    while True:
        with transaction.atomic(using=alias):
            primary_keys = list(
                redaction_queryset(alias=alias, before=before)
                .order_by("pk")
                .values_list("pk", flat=True)[:batch_size]
            )
            if not primary_keys:
                return redacted
            updated = (
                redaction_queryset(alias=alias, before=before)
                .filter(pk__in=primary_keys)
                .update(question="", plan={})
            )
        redacted += updated


def purge_queryset(
    *,
    alias: str,
    before: datetime,
    high_water: int | None = None,
) -> QuerySet[SemanticQueryRun]:
    """Build the selected-alias queryset for purge-eligible audit rows."""

    queryset = SemanticQueryRun.objects.using(alias).filter(created_at__lt=before)
    if high_water is not None:
        queryset = queryset.filter(pk__lte=high_water)
    return queryset


def capture_purge_high_water(*, alias: str, before: datetime) -> int | None:
    """Capture the largest initially eligible primary key for one purge run."""

    return (
        purge_queryset(alias=alias, before=before)
        .order_by("-pk")
        .values_list("pk", flat=True)
        .first()
    )


def purge_in_batches(
    *,
    alias: str,
    before: datetime,
    batch_size: int,
    high_water: int | None,
) -> int:
    """Delete eligible base audit rows in bounded primary-key batches."""

    if high_water is None:
        return 0

    deleted_runs = 0
    model_label = SemanticQueryRun._meta.label
    while True:
        with transaction.atomic(using=alias):
            primary_keys = list(
                purge_queryset(
                    alias=alias,
                    before=before,
                    high_water=high_water,
                )
                .order_by("pk")
                .values_list("pk", flat=True)[:batch_size]
            )
            if not primary_keys:
                return deleted_runs
            _, details = (
                purge_queryset(
                    alias=alias,
                    before=before,
                    high_water=high_water,
                )
                .filter(pk__in=primary_keys)
                .delete()
            )
        deleted_runs += details.get(model_label, 0)
