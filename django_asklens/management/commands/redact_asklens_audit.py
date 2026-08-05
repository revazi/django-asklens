"""Preview or execute bounded redaction of built-in database audit rows."""

from __future__ import annotations

import argparse

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError

from django_asklens.management._audit_lifecycle import (
    DEFAULT_BATCH_SIZE,
    canonical_utc,
    ensure_audit_table,
    parse_before,
    redact_in_batches,
    redaction_queryset,
    validate_batch_size,
)


def _batch_size_argument(value: str) -> int:
    """Adapt internal batch validation to argparse's safe error flow."""

    try:
        return validate_batch_size(value)
    except CommandError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


class Command(BaseCommand):
    """Redact sensitive content from built-in database audit records."""

    help = "Preview or redact question and plan content in AskLens database audits."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare the bounded, preview-by-default command contract."""

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
            help="Apply redaction; omission performs a count-only preview.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Validate, preview, and optionally execute database-only redaction."""

        before = parse_before(options["before"])
        alias = ensure_audit_table(options["database"])
        batch_size = validate_batch_size(options["batch_size"])

        try:
            eligible = redaction_queryset(alias=alias, before=before).count()
        except DatabaseError:
            raise CommandError(
                "AskLens audit redaction could not inspect the selected database."
            ) from None

        self.stdout.write("Operation: redact_asklens_audit")
        self.stdout.write(f"Database alias: {alias}")
        self.stdout.write(f"Cutoff (UTC): {canonical_utc(before)}")
        self.stdout.write(f"Eligible rows (point-in-time): {eligible}")
        self.stdout.write(f"Batch size: {batch_size}")

        if not options["execute"]:
            self.stdout.write("Mode: PREVIEW")
            self.stdout.write(
                "No rows were modified. Re-run with --execute to redact eligible rows."
            )
            return

        try:
            redacted = redact_in_batches(
                alias=alias,
                before=before,
                batch_size=batch_size,
            )
        except DatabaseError:
            raise CommandError(
                "AskLens audit redaction could not update the selected database."
            ) from None

        self.stdout.write("Mode: EXECUTE")
        self.stdout.write(f"Redacted rows: {redacted}")
