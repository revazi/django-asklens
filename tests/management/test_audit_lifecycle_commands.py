"""Acceptance tests for the built-in database audit redaction command."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError
from django.db import DatabaseError, connections
from django.test.utils import CaptureQueriesContext

from django_asklens.management import _audit_lifecycle
from django_asklens.models import SemanticQueryRun

NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)
VALID_BEFORE = "2026-08-05T11:00:00Z"


@pytest.fixture(autouse=True)
def fixed_lifecycle_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep strict past/equal/future command checks deterministic."""

    monkeypatch.setattr(_audit_lifecycle, "_current_time", lambda: NOW)


def _call_redact(*args: str) -> tuple[str, str]:
    stdout = StringIO()
    stderr = StringIO()
    call_command(
        "redact_asklens_audit",
        *args,
        stdout=stdout,
        stderr=stderr,
        no_color=True,
    )
    return stdout.getvalue(), stderr.getvalue()


def _create_run(
    *,
    created_at: datetime,
    question: str = "private question",
    plan: dict | None = None,
    status: str = SemanticQueryRun.Status.SUCCESS,
    row_count: int = 3,
    duration_ms: int | None = 17,
    error: str = "",
    user=None,
    pk: int | None = None,
    using: str = "default",
) -> SemanticQueryRun:
    values = {
        "user": user,
        "question": question,
        "plan": {"private": "plan"} if plan is None else plan,
        "status": status,
        "row_count": row_count,
        "duration_ms": duration_ms,
        "error": error,
    }
    if pk is not None:
        values["pk"] = pk
    run = SemanticQueryRun.objects.using(using).create(**values)
    SemanticQueryRun.objects.using(using).filter(pk=run.pk).update(
        created_at=created_at
    )
    run.refresh_from_db(using=using)
    return run


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("value", "canonical"),
    [
        ("2026-08-05T10:00:00Z", "2026-08-05T10:00:00Z"),
        ("2026-08-05T12:00:00+02:00", "2026-08-05T10:00:00Z"),
        ("2026-08-05T10:00:00.1Z", "2026-08-05T10:00:00.1Z"),
        (
            "2026-08-05T12:00:00.123456+02:00",
            "2026-08-05T10:00:00.123456Z",
        ),
    ],
)
def test_before_accepts_strict_aware_rfc3339_and_outputs_canonical_utc(
    value: str, canonical: str
) -> None:
    stdout, stderr = _call_redact("--before", value)

    assert f"Cutoff (UTC): {canonical}" in stdout
    assert "Batch size: 1000" in stdout
    assert "Mode: PREVIEW" in stdout
    assert stderr == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    [
        "not-a-date",
        "2026-08-05",
        "2026-08-05 10:00:00Z",
        "2026-08-05T10:00:00",
        "2026-08-05t10:00:00Z",
        "2026-08-05T10:00:00z",
        "2026-08-05T10:00:00.1234567Z",
        "2026-08-05T10:00:00+0000",
        "2026-02-30T10:00:00Z",
        "2026-08-05T10:00:00+24:00",
    ],
)
def test_before_rejects_non_contract_timestamp_shapes(value: str) -> None:
    with pytest.raises(CommandError) as error:
        _call_redact("--before", value)

    assert value not in str(error.value)
    assert "offset-aware RFC 3339" in str(error.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value", ["2026-08-05T12:00:00Z", "2026-08-05T12:00:00.000001Z"]
)
def test_before_must_be_strictly_earlier_than_current_aware_time(value: str) -> None:
    with pytest.raises(CommandError) as error:
        _call_redact("--before", value)

    assert value not in str(error.value)
    assert "earlier than the current time" in str(error.value)


@pytest.mark.django_db
def test_before_is_required() -> None:
    with pytest.raises(CommandError):
        _call_redact()


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["0", "-1", "not-an-integer", "10001"])
def test_batch_size_rejects_invalid_or_out_of_range_values(value: str) -> None:
    with pytest.raises(CommandError) as error:
        _call_redact("--before", VALID_BEFORE, "--batch-size", value)

    assert "1 through 10000" in str(error.value)


@pytest.mark.django_db
def test_batch_size_accepts_upper_boundary() -> None:
    stdout, _ = _call_redact("--before", VALID_BEFORE, "--batch-size", "10000")

    assert "Batch size: 10000" in stdout


@pytest.mark.django_db
def test_unknown_database_alias_fails_without_echoing_alias() -> None:
    private_alias = "private-alias-sentinel"

    with pytest.raises(CommandError) as error:
        _call_redact("--before", VALID_BEFORE, "--database", private_alias)

    assert private_alias not in str(error.value)
    assert "configured database alias" in str(error.value)


@pytest.mark.django_db
def test_existing_alias_without_audit_table_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    introspection = connections["default"].introspection
    monkeypatch.setattr(introspection, "table_names", lambda: ["another_table"])

    with pytest.raises(CommandError) as error:
        _call_redact("--before", VALID_BEFORE)

    assert "AskLens audit table is unavailable" in str(error.value)


@pytest.mark.django_db
def test_introspection_failure_does_not_expose_raw_database_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_detail = "private-database-detail-sentinel"

    def fail_introspection() -> list[str]:
        raise DatabaseError(private_detail)

    monkeypatch.setattr(
        connections["default"].introspection,
        "table_names",
        fail_introspection,
    )

    with pytest.raises(CommandError) as error:
        _call_redact("--before", VALID_BEFORE)

    assert private_detail not in str(error.value)
    assert "AskLens audit table is unavailable" in str(error.value)


@pytest.mark.django_db
def test_preview_is_default_counts_eligible_rows_and_performs_zero_writes() -> None:
    eligible = _create_run(created_at=NOW - timedelta(hours=2))
    already_redacted = _create_run(
        created_at=NOW - timedelta(hours=2), question="", plan={}
    )

    stdout, stderr = _call_redact("--before", VALID_BEFORE, "--batch-size", "7")

    eligible.refresh_from_db()
    already_redacted.refresh_from_db()
    assert eligible.question == "private question"
    assert eligible.plan == {"private": "plan"}
    assert already_redacted.question == ""
    assert already_redacted.plan == {}
    assert stdout.splitlines() == [
        "Operation: redact_asklens_audit",
        "Database alias: default",
        "Cutoff (UTC): 2026-08-05T11:00:00Z",
        "Eligible rows (point-in-time): 1",
        "Batch size: 7",
        "Mode: PREVIEW",
        "No rows were modified. Re-run with --execute to redact eligible rows.",
    ]
    assert stderr == ""


@pytest.mark.django_db
def test_execute_redacts_content_and_retains_operational_fields() -> None:
    user = get_user_model().objects.create(username="retained-user-sentinel")
    created_at = NOW - timedelta(hours=2)
    question_only = _create_run(
        created_at=created_at,
        question="question-only-sentinel",
        plan={},
        status=SemanticQueryRun.Status.FAILED,
        row_count=9,
        duration_ms=31,
        error="retained-error-sentinel",
        user=user,
    )
    plan_only = _create_run(
        created_at=created_at,
        question="",
        plan={"private-plan-key": "private-plan-value"},
    )
    equal_boundary = _create_run(created_at=NOW - timedelta(hours=1))
    newer = _create_run(created_at=NOW - timedelta(minutes=30))

    stdout, stderr = _call_redact(
        "--before", VALID_BEFORE, "--batch-size", "1", "--execute"
    )

    question_only.refresh_from_db()
    plan_only.refresh_from_db()
    equal_boundary.refresh_from_db()
    newer.refresh_from_db()
    assert question_only.question == ""
    assert question_only.plan == {}
    assert question_only.user == user
    assert question_only.status == SemanticQueryRun.Status.FAILED
    assert question_only.row_count == 9
    assert question_only.duration_ms == 31
    assert question_only.error == "retained-error-sentinel"
    assert question_only.created_at == created_at
    assert plan_only.question == ""
    assert plan_only.plan == {}
    assert equal_boundary.question == "private question"
    assert equal_boundary.plan == {"private": "plan"}
    assert newer.question == "private question"
    assert newer.plan == {"private": "plan"}
    assert "Eligible rows (point-in-time): 2" in stdout
    assert "Mode: EXECUTE" in stdout
    assert "Redacted rows: 2" in stdout
    assert stderr == ""


@pytest.mark.django_db
@pytest.mark.postgresql
def test_execute_is_idempotent_on_sqlite_and_postgresql() -> None:
    run = _create_run(created_at=NOW - timedelta(hours=2))

    first_stdout, _ = _call_redact("--before", VALID_BEFORE, "--execute")
    second_stdout, _ = _call_redact("--before", VALID_BEFORE, "--execute")

    run.refresh_from_db()
    assert run.question == ""
    assert run.plan == {}
    assert "Redacted rows: 1" in first_stdout
    assert "Eligible rows (point-in-time): 0" in second_stdout
    assert "Redacted rows: 0" in second_stdout


@pytest.mark.django_db
def test_execute_uses_multiple_bounded_batches() -> None:
    for index in range(5):
        _create_run(
            created_at=NOW - timedelta(hours=2),
            question=f"private-batch-question-{index}",
        )

    with CaptureQueriesContext(connections["default"]) as queries:
        stdout, _ = _call_redact(
            "--before", VALID_BEFORE, "--batch-size", "2", "--execute"
        )

    updates = [
        query
        for query in queries.captured_queries
        if query["sql"].lstrip().upper().startswith("UPDATE")
    ]
    assert len(updates) == 3
    assert SemanticQueryRun.objects.exclude(question="").count() == 0
    assert "Redacted rows: 5" in stdout


@pytest.mark.django_db(
    databases={"default", "asklens_read"},
    transaction=True,
)
def test_selected_alias_is_preserved_for_introspection_and_queries() -> None:
    run = _create_run(
        using="asklens_read",
        created_at=NOW - timedelta(hours=2),
        question="alias-question-sentinel",
    )

    with CaptureQueriesContext(connections["default"]) as default_queries:
        with CaptureQueriesContext(connections["asklens_read"]) as alias_queries:
            stdout, _ = _call_redact(
                "--before",
                VALID_BEFORE,
                "--database",
                "asklens_read",
                "--execute",
            )

    run.refresh_from_db(using="asklens_read")
    assert run.question == ""
    assert run.plan == {}
    assert default_queries.captured_queries == []
    assert alias_queries.captured_queries
    assert "Database alias: asklens_read" in stdout


@pytest.mark.django_db
def test_output_excludes_content_user_error_and_row_id_sentinels() -> None:
    user_sentinel = "unique-private-user-sentinel"
    question_sentinel = "unique-private-question-sentinel"
    plan_key_sentinel = "unique-private-plan-key-sentinel"
    plan_value_sentinel = "unique-private-plan-value-sentinel"
    error_sentinel = "unique-private-error-sentinel"
    user = get_user_model().objects.create(username=user_sentinel)
    run = _create_run(
        pk=87_654_321,
        created_at=NOW - timedelta(hours=2),
        question=question_sentinel,
        plan={plan_key_sentinel: plan_value_sentinel},
        error=error_sentinel,
        user=user,
    )

    stdout, stderr = _call_redact(
        "--before", VALID_BEFORE, "--batch-size", "37", "--execute"
    )
    combined = f"{stdout}\n{stderr}"

    for private_value in (
        question_sentinel,
        plan_key_sentinel,
        plan_value_sentinel,
        user_sentinel,
        error_sentinel,
        str(run.pk),
    ):
        assert private_value not in combined
    assert "SELECT" not in combined.upper()
    assert "UPDATE" not in combined.upper()


@pytest.mark.django_db
def test_custom_audit_mode_and_trap_sink_are_not_consulted(settings) -> None:
    events: list[object] = []

    def trap_sink(event: object) -> None:
        events.append(event)
        raise AssertionError("custom sink must not be invoked")

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "custom",
        "AUDIT_SINK": trap_sink,
        "AUDIT_INCLUDE_CONTENT": True,
    }
    run = _create_run(created_at=NOW - timedelta(hours=2))

    _call_redact("--before", VALID_BEFORE, "--execute")

    run.refresh_from_db()
    assert run.question == ""
    assert run.plan == {}
    assert events == []


def test_command_is_discovered_and_helper_is_not_a_command() -> None:
    commands = get_commands()

    assert commands["redact_asklens_audit"] == "django_asklens"
    assert "_audit_lifecycle" not in commands
