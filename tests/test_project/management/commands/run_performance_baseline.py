"""Run a fixed synthetic AskLens query corpus for local performance baselines."""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from argparse import ArgumentTypeError
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from statistics import mean
from time import perf_counter_ns
from types import SimpleNamespace
from typing import Any

import django
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings

from django_asklens.querying import execute_asklens_query_request
from tests.test_project.management.commands.seed_complex_test_project import (
    SEED_PROFILES,
)
from tests.test_project.models import (
    BillingDocument,
    BillingLine,
    Facility,
    MemberProfile,
)


class PerformanceQueryProfile(str):
    """Allowed bounded query-profile names."""

    COMPACT = "compact"
    BASELINE = "baseline"


DEFAULT_DATASET_PROFILE = "medium"
DEFAULT_ITERATIONS = 3
DEFAULT_MAX_ITERATIONS = 100
DEFAULT_WARMUPS = 1
DEFAULT_MAX_WARMUPS = 20
DEFAULT_ARTIFACT_DIR = ".asklens-performance-baseline"
DEFAULT_ARTIFACT_NAME = "latest"
DEFAULT_QUERY_PROFILE = PerformanceQueryProfile.BASELINE
DEFAULT_USER = "admin"


@dataclass(frozen=True, slots=True)
class BaselineQuery:
    """Fixed query definition for baseline measurement."""

    name: str
    resource: str
    intent: str
    plan: dict[str, Any]
    expected_columns: tuple[tuple[str, str], ...]
    expected_limit_scope: str
    expected_truncated: bool | None = None


BASELINE_QUERIES: tuple[BaselineQuery, ...] = (
    BaselineQuery(
        name="member-directory-truncated",
        resource="members",
        intent="list",
        expected_columns=(
            ("facility.name", "string"),
            ("gender", "enum"),
            ("created_via_portal", "boolean"),
            ("created_at", "datetime"),
        ),
        expected_limit_scope="rows",
        expected_truncated=True,
        plan={
            "resource": "members",
            "intent": "list",
            "select": [
                "facility.name",
                "gender",
                "created_via_portal",
                "created_at",
            ],
            "order_by": [
                {"field": "facility.name", "direction": "asc"},
                {"field": "created_at", "direction": "asc"},
            ],
            "limit": 3,
        },
    ),
    BaselineQuery(
        name="member-count-by-gender-and-portal",
        resource="members",
        intent="aggregate",
        expected_columns=(("gender", "enum"), ("member_count", "integer")),
        expected_limit_scope="groups",
        plan={
            "resource": "members",
            "intent": "aggregate",
            "filters": [
                {
                    "field": "created_via_portal",
                    "op": "eq",
                    "value": True,
                }
            ],
            "group_by": [{"field": "gender"}],
            "metrics": [{"metric": "member_count"}],
            "order_by": [{"metric": "member_count", "direction": "desc"}],
            "limit": 20,
        },
    ),
    BaselineQuery(
        name="billing-revenue-by-product",
        resource="billing_lines",
        intent="aggregate",
        expected_columns=(
            ("product_name", "string"),
            ("gross_revenue", "integer"),
        ),
        expected_limit_scope="groups",
        plan={
            "resource": "billing_lines",
            "intent": "aggregate",
            "filters": [
                {"field": "billing_document.status", "op": "eq", "value": "PAID"}
            ],
            "group_by": [{"field": "product_name"}],
            "metrics": [{"metric": "gross_revenue"}],
            "order_by": [{"metric": "gross_revenue", "direction": "desc"}],
            "limit": 20,
        },
    ),
)

COMPACT_QUERIES: tuple[BaselineQuery, ...] = (BASELINE_QUERIES[0],)

_QUERY_PROFILES = {
    PerformanceQueryProfile.COMPACT: COMPACT_QUERIES,
    PerformanceQueryProfile.BASELINE: BASELINE_QUERIES,
}

LIMITATION_NOTES = (
    "Synthetic dataset only; synthetic rows only.",
    "Host-dependent timing; wall and query durations are not SLA commitments.",
    "Single machine/process context only; cache warm-state may vary between runs.",
    "No production or pilot guarantee is implied by this artifact.",
)


class _CountOnlyAuditSink:
    """Collect only event counts and reject sensitive payload content."""

    __slots__ = ("_event_count",)

    def __init__(self) -> None:
        self._event_count = 0

    def __call__(self, event: Mapping[str, Any]) -> None:
        question = event.get("question")
        if question:
            raise ValueError("Audit sink received unredacted query question content.")
        plan = event.get("plan")
        if isinstance(plan, Mapping):
            if plan:
                raise ValueError(
                    "Audit sink received unredacted semantic plan content."
                )
        elif plan:
            raise ValueError("Audit sink received unredacted semantic plan content.")
        self._event_count += 1

    def count(self) -> int:
        return self._event_count


class Command(BaseCommand):
    """Run a fixed, redacted performance baseline against seeded synthetic data."""

    help = (
        "Run fixed AskLens query corpus measurements and emit a redacted JSON "
        "artifact for local synthetic performance checks."
    )

    def add_arguments(self, parser) -> None:
        """Configure corpus, bounds, and artifact output."""

        parser.add_argument(
            "--user",
            default=DEFAULT_USER,
            help="Seeded demo user to run the baseline as.",
        )
        parser.add_argument(
            "--dataset-profile",
            "--size",
            dest="dataset_profile",
            default=DEFAULT_DATASET_PROFILE,
            choices=tuple(SEED_PROFILES),
            help=(
                "Seeded synthetic dataset profile: small, medium, or large "
                "(default: medium)."
            ),
        )
        parser.add_argument(
            "--query-profile",
            default=DEFAULT_QUERY_PROFILE,
            choices=(
                PerformanceQueryProfile.COMPACT,
                PerformanceQueryProfile.BASELINE,
            ),
            help="Bounded query corpus profile to execute.",
        )
        parser.add_argument(
            "--iterations",
            default=DEFAULT_ITERATIONS,
            type=_bounded_int_argument(
                min_value=1,
                max_value=DEFAULT_MAX_ITERATIONS,
            ),
            help=(
                f"Measured iterations per query plan ({1}..{DEFAULT_MAX_ITERATIONS})."
            ),
        )
        parser.add_argument(
            "--warmups",
            default=DEFAULT_WARMUPS,
            type=_bounded_int_argument(
                min_value=0,
                max_value=DEFAULT_MAX_WARMUPS,
            ),
            help=(f"Warmup iterations per query plan ({0}..{DEFAULT_MAX_WARMUPS})."),
        )
        parser.add_argument(
            "--artifact-dir",
            default=DEFAULT_ARTIFACT_DIR,
            help=(
                "Artifact directory. Used when --output is not set. "
                f"Defaults to {DEFAULT_ARTIFACT_DIR}/"
            ),
        )
        parser.add_argument(
            "--artifact-name",
            default=DEFAULT_ARTIFACT_NAME,
            help="Artifact file name without extension when --output is unset.",
        )
        parser.add_argument(
            "--output",
            default=None,
            type=_validate_output_path,
            help="Explicit artifact output path (JSON).",
        )
        parser.add_argument(
            "--commit",
            default=None,
            type=_validate_commit_argument,
            help="Exact 40-hex commit SHA associated with the baseline run.",
        )

    def handle(self, *args, **options) -> None:
        """Run the baseline corpus and write a redacted JSON artifact."""

        del args
        ensure_complex_resources_registered()

        dataset_profile = _validate_dataset_profile(options["dataset_profile"])
        query_profile = _validate_query_profile(options["query_profile"])
        iterations = _validate_int_option(
            options["iterations"],
            min_value=1,
            max_value=DEFAULT_MAX_ITERATIONS,
            name="iterations",
        )
        warmups = _validate_int_option(
            options["warmups"],
            min_value=0,
            max_value=DEFAULT_MAX_WARMUPS,
            name="warmups",
        )
        commit = options["commit"]
        if commit is None:
            commit = _collect_default_commit()

        user = get_demo_user(options["user"])
        request = _build_request(user)
        audit_sink = _CountOnlyAuditSink()
        baseline_settings = dict(django_settings.DJANGO_ASKLENS)
        baseline_settings.update(
            {
                "AUDIT_MODE": "custom",
                "AUDIT_INCLUDE_CONTENT": False,
                "AUDIT_SINK": audit_sink,
            }
        )

        cases: list[dict[str, Any]] = []
        with override_settings(DJANGO_ASKLENS=baseline_settings):
            for query in _QUERY_PROFILES[query_profile]:
                result = _run_query_profile(
                    request=request,
                    query=query,
                    iterations=iterations,
                    warmups=warmups,
                    audit_sink=audit_sink,
                )
                cases.append(_build_case_payload(query=query, result=result))

        payload = {
            "evidence_kind": "synthetic_query_performance",
            "status": "success",
            "synthetic": True,
            "generated_at": _utc_now_iso(),
            "environment": _collect_environment(),
            "dataset": _collect_dataset_payload(dataset_profile),
            "run_config": {
                "query_profile": query_profile,
                "dataset_profile": dataset_profile.name,
                "iterations": {
                    "measured": iterations,
                    "warmups": warmups,
                },
                "audit_mode": "custom_metadata_discard",
            },
            "cases": cases,
            "limitations": list(LIMITATION_NOTES),
            "commit": commit,
        }

        output = _resolve_output_path(
            output=options["output"],
            artifact_dir=Path(options["artifact_dir"]),
            artifact_name=options["artifact_name"],
            query_profile=query_profile,
            dataset_profile=dataset_profile.name,
            iterations=iterations,
            warmups=warmups,
        )
        output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(self.style.SUCCESS(f"Saved performance baseline: {output}"))


def _run_query_profile(
    *,
    request,
    query: BaselineQuery,
    iterations: int,
    warmups: int,
    audit_sink: _CountOnlyAuditSink,
) -> dict[str, Any]:
    """Run warmups then measured query calls and return redacted artifact fields."""

    for _ in range(warmups):
        _run_baseline_query(request=request, query=query)

    starting_events = audit_sink.count()
    samples = [
        _run_baseline_query(request=request, query=query) for _ in range(iterations)
    ]
    audit_events = audit_sink.count() - starting_events
    if audit_events != iterations:
        raise CommandError(
            f"Baseline query {query.name!r} emitted {audit_events} audit events; "
            f"expected {iterations} measured events."
        )

    first_result_metadata = samples[0]["result_metadata"]
    if not all(
        sample["result_metadata"] == first_result_metadata for sample in samples
    ):
        raise CommandError(
            f"Baseline query {query.name!r} returned inconsistent result metadata "
            f"between measured iterations."
        )

    durations = [sample["duration_ms"] for sample in samples]
    wall_durations = [sample["wall_duration_ms"] for sample in samples]
    query_counts = [sample["query_count"] for sample in samples]
    row_counts = [sample["row_count"] for sample in samples]

    return {
        "samples": [_serialize_sample(sample) for sample in samples],
        "durations": summarize_numeric_series(durations),
        "wall_durations": summarize_numeric_series(wall_durations),
        "query_counts": summarize_numeric_series(query_counts),
        "row_counts": summarize_numeric_series(row_counts),
        "result_metadata": first_result_metadata,
        "audit_event_count": audit_events,
    }


def _run_baseline_query(*, request, query: BaselineQuery) -> dict[str, Any]:
    """Execute one fully validated synthetic query and collect redacted metrics."""

    with CaptureQueriesContext(connection) as captured:
        start_ns = perf_counter_ns()
        response = execute_asklens_query_request(
            request,
            question=f"Performance baseline: {query.name}",
            provided_plan=query.plan,
            include_presentation=False,
        )
        wall_duration_ms = _wall_duration_ms(start_ns, perf_counter_ns())

    if response.response_type != "query":
        error = response.payload.get("error", {})
        error_code = (
            error.get("code", "unknown") if isinstance(error, dict) else "unknown"
        )
        raise CommandError(
            f"Baseline query {query.name!r} returned {response.response_type} "
            f"with error code {error_code}."
        )

    payload = response.payload
    if not isinstance(payload, Mapping):
        raise CommandError(
            f"Baseline query {query.name!r} produced an invalid payload."
        )

    _validate_result_columns(
        query=query,
        value=payload.get("columns"),
    )

    duration_ms = payload.get("duration_ms")
    row_count = payload.get("row_count")
    if not isinstance(duration_ms, int) or not isinstance(row_count, int):
        raise CommandError(
            f"Baseline query {query.name!r} produced invalid result metrics."
        )

    result_metadata = payload.get("result_metadata")
    if not isinstance(result_metadata, dict):
        raise CommandError(f"Baseline query {query.name!r} omitted result metadata.")

    limit = result_metadata.get("limit")
    limit_scope = result_metadata.get("limit_scope")
    truncated = result_metadata.get("truncated")
    if not isinstance(limit, int) or limit < 0:
        raise CommandError(
            f"Baseline query {query.name!r} reported an invalid result limit."
        )
    if not isinstance(limit_scope, str):
        raise CommandError(
            f"Baseline query {query.name!r} reported an invalid limit scope."
        )
    if not isinstance(truncated, bool):
        raise CommandError(
            f"Baseline query {query.name!r} reported non-boolean truncation."
        )
    if limit_scope != query.expected_limit_scope:
        raise CommandError(
            f"Baseline query {query.name!r} reported unexpected limit scope "
            f"{limit_scope!r}."
        )
    if row_count > limit:
        raise CommandError(
            f"Baseline query {query.name!r} returned {row_count} rows "
            f"over limit {limit}."
        )
    if row_count < limit and truncated:
        raise CommandError(
            f"Baseline query {query.name!r} reported truncated=True with only "
            f"{row_count} rows and limit {limit}."
        )
    if row_count < limit:
        expected_truncated = False
    elif row_count == limit:
        expected_truncated = truncated
    else:
        expected_truncated = True
    if query.expected_truncated is True and not expected_truncated:
        raise CommandError(
            f"Baseline query {query.name!r} did not truncate as expected."
        )
    if query.expected_truncated is False and expected_truncated:
        raise CommandError(f"Baseline query {query.name!r} truncated unexpectedly.")

    return {
        "duration_ms": duration_ms,
        "wall_duration_ms": wall_duration_ms,
        "query_count": len(captured.captured_queries),
        "row_count": row_count,
        "result_metadata": {
            "limit": limit,
            "limit_scope": limit_scope,
            "truncated": truncated,
        },
    }


def _wall_duration_ms(start_ns: int, end_ns: int) -> float:
    """Return wall-clock milliseconds with millisecond precision."""

    if end_ns < start_ns:
        raise CommandError("Wall clock measurement produced a negative duration.")
    return round((end_ns - start_ns) / 1_000_000, 3)


def _serialize_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Serialize one redacted query sample for artifact emission."""

    return {
        "duration_ms": sample["duration_ms"],
        "wall_duration_ms": sample["wall_duration_ms"],
        "query_count": sample["query_count"],
        "row_count": sample["row_count"],
    }


def _validate_result_columns(*, query: BaselineQuery, value: object) -> None:
    """Assert exact query output column shape for deterministic baselines."""

    if not isinstance(value, list):
        raise CommandError(
            f"Baseline query {query.name!r} omitted or returned malformed columns."
        )
    expected_columns = query.expected_columns
    if len(value) != len(expected_columns):
        raise CommandError(
            f"Baseline query {query.name!r} changed columns; expected "
            f"{len(expected_columns)} columns, got {len(value)}."
        )
    for index, (expected_key, expected_type) in enumerate(expected_columns):
        column = value[index]
        if not isinstance(column, Mapping):
            raise CommandError(
                f"Baseline query {query.name!r} returned malformed column "
                f"at position {index}."
            )
        if column.get("key") != expected_key:
            raise CommandError(
                f"Baseline query {query.name!r} returned unexpected column key at "
                f"position {index}: {column.get('key')!r}."
            )
        if column.get("type") != expected_type:
            raise CommandError(
                f"Baseline query {query.name!r} returned unexpected column type for "
                f"{expected_key!r}."
            )


def _build_case_payload(
    *, query: BaselineQuery, result: dict[str, Any]
) -> dict[str, Any]:
    """Build a deterministic redacted case payload."""

    return {
        "name": query.name,
        "resource": query.resource,
        "intent": query.intent,
        "status": "success",
        "samples": result["samples"],
        "duration_ms": result["durations"],
        "wall_duration_ms": result["wall_durations"],
        "query_count": result["query_counts"],
        "row_count": result["row_counts"],
        "result_metadata": result["result_metadata"],
        "audit": {
            "mode": "custom_metadata_discard",
            "event_count": result["audit_event_count"],
        },
    }


def summarize_numeric_series(
    values: list[int] | list[float], *, include_mean: bool = True
) -> dict[str, Any]:
    """Summarize numeric timing/count metrics with nearest-rank percentiles."""

    if not values:
        raise CommandError("Cannot summarize an empty numeric series.")
    sorted_values = sorted(values)
    summary = {
        "count": len(sorted_values),
        "min": sorted_values[0],
        "p50": _nearest_rank(sorted_values, 50),
        "p95": _nearest_rank(sorted_values, 95),
        "max": sorted_values[-1],
    }
    if include_mean:
        summary["mean"] = round(float(mean(values)), 3)
    return summary


def _nearest_rank(
    sorted_values: list[int] | list[float], percentile: float
) -> int | float:
    """Return nearest-rank percentile: ceil(p*n)-1 index in 1-indexed samples."""

    if not sorted_values:
        raise CommandError("Cannot calculate percentile of an empty series.")
    if not (0 <= percentile <= 100):
        raise CommandError("Percentile must be between 0 and 100.")
    n = len(sorted_values)
    position = max(1, ceil((percentile / 100) * n))
    index = position - 1
    return sorted_values[index]


def _collect_environment() -> dict[str, Any]:
    """Collect only non-sensitive environment metadata."""

    connection.ensure_connection()
    vendor = connection.vendor
    return {
        "python_version": sys.version.split(" ", maxsplit=1)[0],
        "django_version": django.get_version(),
        "database_vendor": vendor,
        "database_version": _database_server_version(vendor=vendor),
    }


def _database_server_version(*, vendor: str) -> str:
    """Collect the server version without network or credentials."""

    if vendor == "sqlite":
        return sqlite3.sqlite_version

    if connection.connection is None or vendor != "postgresql":
        return "unknown"
    try:
        server_version = connection.connection.info.server_version
    except AttributeError:
        return "unknown"
    major = server_version // 10000
    minor = server_version % 10000
    return f"{major}.{minor}"


def _collect_dataset_payload(profile) -> dict[str, Any]:
    """Emit safe synthetic dataset dimensions for later comparison."""

    return {
        "profile": {
            "name": profile.name,
            "scaled_tenant_count": profile.scaled_tenant_count,
            "members_per_tenant": profile.members_per_tenant,
            "billing_months": profile.billing_months,
            "schedule_weeks": profile.schedule_weeks,
            "batch_size": profile.batch_size,
        },
        "counts": {
            "facilities": Facility.objects.count(),
            "members": MemberProfile.objects.count(),
            "billing_documents": BillingDocument.objects.count(),
            "billing_lines": BillingLine.objects.count(),
        },
    }


def _resolve_output_path(
    *,
    output: str | None,
    artifact_dir: Path,
    artifact_name: str,
    query_profile: str,
    dataset_profile: str,
    iterations: int,
    warmups: int,
) -> Path:
    """Return an explicit or default artifact output path."""

    if output:
        artifact_path = Path(output)
    else:
        artifact_name = _validate_artifact_name(artifact_name)
        artifact_path = artifact_dir / (
            f"{artifact_name}-{query_profile}-profile-{dataset_profile}-"
            f"i{iterations}-w{warmups}.json"
        )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    if artifact_path.suffix != ".json":
        artifact_path = artifact_path.with_suffix(artifact_path.suffix + ".json")
    return artifact_path


def _validate_query_profile(value: str) -> str:
    """Validate and return the selected query profile."""

    if value not in _QUERY_PROFILES:
        raise CommandError(
            f"Unknown query profile {value!r}. Expected compact or baseline."
        )
    return PerformanceQueryProfile(value)


def _validate_dataset_profile(value: str):
    """Validate and return a known seed profile."""

    if value not in SEED_PROFILES:
        raise CommandError(
            f"Unknown dataset profile {value!r}. Expected small, medium, or large."
        )
    return SEED_PROFILES[value]


def _validate_int_option(
    value: object,
    *,
    min_value: int,
    max_value: int,
    name: str,
) -> int:
    """Return a bounded integer and reject malformed values."""

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CommandError(
            f"Expected {name} as an integer in "
            f"[{min_value}, {max_value}], got: {value!r}."
        ) from exc
    if not (min_value <= parsed <= max_value):
        raise CommandError(
            f"Expected {name} in [{min_value}, {max_value}], got: {value!r}."
        )
    return parsed


def _collect_default_commit() -> str:
    """Return the current checked-out commit for artifact lineage."""

    try:
        output = subprocess.check_output(
            ("git", "rev-parse", "HEAD"),
            text=True,
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CommandError(
            "Unable to resolve current commit SHA. Pass --commit explicitly."
        ) from exc

    commit = output.strip()
    try:
        return _validate_commit_argument(commit)
    except ArgumentTypeError as exc:
        raise CommandError(
            "Current HEAD commit is not a valid 40-character lowercase hex string."
        ) from exc


def _validate_commit_argument(value: str) -> str:
    """Validate a full 40-character git commit SHA."""

    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ArgumentTypeError(
            "Commit SHA must be a 40-character lowercase hexadecimal string."
        )
    return value


def _bounded_int_argument(*, min_value: int, max_value: int):
    """Create a bounded integer parser."""

    def _parser(value: str) -> int:
        if not value.isdigit():
            raise ArgumentTypeError(
                f"Expected an integer in [{min_value}, {max_value}], got: {value!r}."
            )
        parsed = int(value)
        if not (min_value <= parsed <= max_value):
            raise ArgumentTypeError(
                f"Expected an integer in [{min_value}, {max_value}], got: {value!r}."
            )
        return parsed

    return _parser


def _validate_output_path(value: str) -> str:
    """Validate output path input and reject unsafe placeholders."""

    if not value:
        raise ArgumentTypeError("Output path must be a non-empty path.")
    if "\x00" in value:
        raise ArgumentTypeError("Output path cannot contain null bytes.")
    return value


def _validate_artifact_name(value: str) -> str:
    """Validate artifact file names supplied via --artifact-name."""

    if not value:
        raise ArgumentTypeError("artifact-name must be non-empty.")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", value):
        raise ArgumentTypeError(
            "artifact-name must be 1-80 characters of A-Z, a-z, 0-9, ., _, or -."
        )
    return value


def _utc_now_iso() -> str:
    """Return a UTC timestamp for artifact metadata."""

    return datetime.now(UTC).isoformat(timespec="seconds")


def get_demo_user(username: str):
    """Return a seeded demo user or raise a clear command error."""

    user_model = get_user_model()
    try:
        return user_model.objects.get(username=username)
    except user_model.DoesNotExist as exc:
        msg = (
            f"Demo user {username!r} does not exist. Run "
            "`python -m django seed_complex_test_project` first."
        )
        raise CommandError(msg) from exc


@dataclass(frozen=True, slots=True)
class _BaselinePermissionUser:
    """Proxy user with deterministic permission strings for baseline execution."""

    user: Any
    permissions: tuple[str, ...]

    @property
    def is_authenticated(self) -> bool:
        return bool(getattr(self.user, "is_authenticated", False))

    def get_all_permissions(self) -> frozenset[str]:
        return frozenset(self.permissions)

    def get_user_permissions(self, obj: Any = None) -> frozenset[str]:
        del obj
        return frozenset(self.permissions)

    def get_group_permissions(self, obj: Any = None) -> frozenset[str]:
        del obj
        return frozenset()

    def has_perm(self, perm: str, obj: Any = None) -> bool:
        del obj
        return perm in self.permissions

    @property
    def id(self) -> int | None:
        return self.user.id

    @property
    def pk(self) -> int | None:
        return self.user.pk

    def __int__(self) -> int:
        assert self.user.id is not None
        return int(self.user.id)

    def __index__(self) -> int:
        return int(self)

    def __getattr__(self, name: str) -> object:
        return getattr(self.user, name)


def _build_request(user) -> Any:
    """Build a deterministic request object for internal execution helpers."""

    from tests.test_project.permissions import get_request_permissions

    request_permissions = get_request_permissions(SimpleNamespace(user=user))
    return SimpleNamespace(
        user=_BaselinePermissionUser(
            user=user,
            permissions=tuple(sorted(request_permissions)),
        )
    )


def ensure_complex_resources_registered() -> None:
    """Avoid re-import cycles and keep runtime registration explicit."""

    from tests.test_project.asklens_registry import ensure_complex_resources_registered

    ensure_complex_resources_registered()
