"""Acceptance tests for bounded built-in database audit purging."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError
from django.db import connections
from django.db.models import QuerySet
from django.db.models.signals import post_delete, pre_delete
from django.test.utils import CaptureQueriesContext

from django_asklens.management import _audit_lifecycle
from django_asklens.management.commands import purge_asklens_audit as purge_command
from django_asklens.management.commands.purge_asklens_audit import (
    Command as PurgeCommand,
)
from django_asklens.management.commands.redact_asklens_audit import (
    Command as RedactCommand,
)
from django_asklens.models import SemanticQueryRun

NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)
VALID_BEFORE = "2026-08-05T11:00:00Z"


@pytest.fixture(autouse=True)
def fixed_lifecycle_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the shared strict cutoff contract deterministic."""

    monkeypatch.setattr(_audit_lifecycle, "_current_time", lambda: NOW)


def _call_purge(*args: str) -> tuple[str, str]:
    stdout = StringIO()
    stderr = StringIO()
    call_command(
        "purge_asklens_audit",
        *args,
        stdout=stdout,
        stderr=stderr,
        no_color=True,
    )
    return stdout.getvalue(), stderr.getvalue()


def _create_run(
    *,
    created_at: datetime,
    question: str = "private purge question",
    plan: dict | None = None,
    error: str = "",
    user=None,
    pk: int | None = None,
    using: str = "default",
) -> SemanticQueryRun:
    values = {
        "user": user,
        "question": question,
        "plan": {"private": "purge plan"} if plan is None else plan,
        "status": SemanticQueryRun.Status.SUCCESS,
        "row_count": 3,
        "duration_ms": 17,
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


def _lifecycle_actions(command, name: str) -> dict[str, object]:
    parser = command.create_parser("manage.py", name)
    return {
        action.dest: action
        for action in parser._actions
        if action.dest in {"before", "database", "batch_size", "execute"}
    }


def test_commands_are_discovered_with_exact_shared_options_and_defaults() -> None:
    commands = get_commands()
    assert commands["redact_asklens_audit"] == "django_asklens"
    assert commands["purge_asklens_audit"] == "django_asklens"
    assert "_audit_lifecycle" not in commands

    redact = _lifecycle_actions(RedactCommand(), "redact_asklens_audit")
    purge = _lifecycle_actions(PurgeCommand(), "purge_asklens_audit")
    assert (
        set(redact)
        == set(purge)
        == {
            "before",
            "database",
            "batch_size",
            "execute",
        }
    )
    for destination in redact:
        assert redact[destination].option_strings == purge[destination].option_strings
        assert redact[destination].required == purge[destination].required
        assert redact[destination].default == purge[destination].default
        assert redact[destination].type is purge[destination].type

    assert purge["before"].option_strings == ["--before"]
    assert purge["before"].required is True
    assert purge["database"].option_strings == ["--database"]
    assert purge["database"].default == "default"
    assert purge["batch_size"].option_strings == ["--batch-size"]
    assert purge["batch_size"].default == 1_000
    assert purge["execute"].option_strings == ["--execute"]
    assert purge["execute"].default is False

    help_text = (
        PurgeCommand().create_parser("manage.py", "purge_asklens_audit").format_help()
    )
    assert "--before RFC3339" in help_text
    assert "--database DATABASE" in help_text
    assert "--batch-size BATCH_SIZE" in help_text
    assert "--execute" in help_text
    normalized_help = " ".join(help_text.lower().split())
    assert "preview" in normalized_help
    assert "irreversible" in normalized_help
    assert "signals" in normalized_help
    assert "earlier committed batches" in normalized_help
    assert "backup/restore" in normalized_help


@pytest.mark.django_db
def test_purge_reuses_strict_cutoff_and_canonical_utc_output() -> None:
    stdout, stderr = _call_purge("--before", "2026-08-05T12:00:00.1+02:00")

    assert "Cutoff (UTC): 2026-08-05T10:00:00.1Z" in stdout
    assert "Batch size: 1000" in stdout
    assert "Mode: PREVIEW" in stdout
    assert stderr == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--before", "bad"), "offset-aware RFC 3339"),
        (("--before", "2026-08-05T12:00:00Z"), "earlier than the current time"),
        (("--before", VALID_BEFORE, "--batch-size", "0"), "1 through 10000"),
        (
            ("--before", VALID_BEFORE, "--batch-size", "not-an-integer"),
            "1 through 10000",
        ),
        (("--before", VALID_BEFORE, "--batch-size", "10001"), "1 through 10000"),
    ],
)
def test_purge_inherits_safe_cutoff_and_batch_failures(
    args: tuple[str, ...], message: str
) -> None:
    with pytest.raises(CommandError) as error:
        _call_purge(*args)

    assert message in str(error.value)
    if args[0] == "--before" and args[1] != VALID_BEFORE:
        assert args[1] not in str(error.value)


@pytest.mark.django_db
def test_purge_requires_before() -> None:
    with pytest.raises(CommandError):
        _call_purge()


@pytest.mark.django_db
def test_purge_rejects_unknown_alias_without_echoing_it() -> None:
    private_alias = "private-purge-alias-sentinel"

    with pytest.raises(CommandError) as error:
        _call_purge("--before", VALID_BEFORE, "--database", private_alias)

    assert private_alias not in str(error.value)
    assert "configured database alias" in str(error.value)


@pytest.mark.django_db
def test_purge_rejects_existing_alias_without_audit_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        connections["default"].introspection,
        "table_names",
        lambda: ["another_table"],
    )

    with pytest.raises(CommandError) as error:
        _call_purge("--before", VALID_BEFORE)

    assert "AskLens audit table is unavailable" in str(error.value)


@pytest.mark.django_db
def test_preview_counts_all_old_rows_and_performs_zero_writes() -> None:
    old = _create_run(created_at=NOW - timedelta(hours=2))
    equal = _create_run(created_at=NOW - timedelta(hours=1))
    newer = _create_run(created_at=NOW - timedelta(minutes=30))

    with CaptureQueriesContext(connections["default"]) as queries:
        stdout, stderr = _call_purge("--before", VALID_BEFORE, "--batch-size", "7")

    remaining = SemanticQueryRun.objects.filter(
        pk__in=[old.pk, equal.pk, newer.pk]
    ).count()
    assert remaining == 3
    assert not any(
        query["sql"].lstrip().upper().startswith(("DELETE", "UPDATE", "INSERT"))
        for query in queries.captured_queries
    )
    assert stdout.splitlines() == [
        "Operation: purge_asklens_audit",
        "Database alias: default",
        "Cutoff (UTC): 2026-08-05T11:00:00Z",
        "Eligible rows (point-in-time): 1",
        "Batch size: 7",
        (
            "Warning: Purge is irreversible; normal Django delete signals and "
            "relationship behavior apply."
        ),
        (
            "Warning: Earlier completed batches can remain deleted if a later "
            "batch fails; external signal effects cannot be rolled back."
        ),
        "Warning: Test backup/restore before using --execute.",
        "Mode: PREVIEW",
        (
            "No rows were deleted. Re-run with --execute to permanently delete "
            "eligible rows."
        ),
    ]
    assert stderr == ""


@pytest.mark.django_db
def test_execute_deletes_only_rows_strictly_older_than_cutoff() -> None:
    old = _create_run(created_at=NOW - timedelta(hours=2))
    equal = _create_run(created_at=NOW - timedelta(hours=1))
    newer = _create_run(created_at=NOW - timedelta(minutes=30))

    stdout, stderr = _call_purge("--before", VALID_BEFORE, "--execute")

    assert not SemanticQueryRun.objects.filter(pk=old.pk).exists()
    assert SemanticQueryRun.objects.filter(pk=equal.pk).exists()
    assert SemanticQueryRun.objects.filter(pk=newer.pk).exists()
    assert "Eligible rows (point-in-time): 1" in stdout
    assert "Warning: Purge is irreversible" in stdout
    assert stdout.index("Warning: Purge") < stdout.index("Mode: EXECUTE")
    assert "Mode: EXECUTE" in stdout
    assert "Deleted SemanticQueryRun rows: 1" in stdout
    assert stderr == ""


@pytest.mark.django_db
@pytest.mark.postgresql
def test_purge_execute_is_idempotent_on_sqlite_and_postgresql() -> None:
    old = _create_run(created_at=NOW - timedelta(hours=2))

    first_stdout, _ = _call_purge("--before", VALID_BEFORE, "--execute")
    second_stdout, _ = _call_purge("--before", VALID_BEFORE, "--execute")

    assert not SemanticQueryRun.objects.filter(pk=old.pk).exists()
    assert "Deleted SemanticQueryRun rows: 1" in first_stdout
    assert "Eligible rows (point-in-time): 0" in second_stdout
    assert "Deleted SemanticQueryRun rows: 0" in second_stdout


@pytest.mark.django_db
def test_execute_uses_three_delete_batches_for_five_rows() -> None:
    for index in range(5):
        _create_run(
            created_at=NOW - timedelta(hours=2),
            question=f"private-purge-batch-{index}",
        )

    with CaptureQueriesContext(connections["default"]) as queries:
        stdout, _ = _call_purge(
            "--before", VALID_BEFORE, "--batch-size", "2", "--execute"
        )

    deletes = [
        query
        for query in queries.captured_queries
        if query["sql"].lstrip().upper().startswith("DELETE")
        and SemanticQueryRun._meta.db_table.upper() in query["sql"].upper()
    ]
    assert len(deletes) == 3
    assert SemanticQueryRun.objects.count() == 0
    assert "Deleted SemanticQueryRun rows: 5" in stdout


@pytest.mark.django_db
def test_concurrent_zero_delete_continues_and_reports_only_own_deletions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _create_run(created_at=NOW - timedelta(hours=2))
    second = _create_run(created_at=NOW - timedelta(hours=2))
    original_delete = QuerySet.delete
    intercepted = False

    def delete_after_concurrent_removal(queryset):
        nonlocal intercepted
        if not intercepted:
            intercepted = True
            selected = list(queryset.values_list("pk", flat=True))
            concurrent = SemanticQueryRun.objects.filter(pk__in=selected)
            original_delete(concurrent)
        return original_delete(queryset)

    monkeypatch.setattr(QuerySet, "delete", delete_after_concurrent_removal)

    stdout, _ = _call_purge("--before", VALID_BEFORE, "--batch-size", "1", "--execute")

    assert not SemanticQueryRun.objects.filter(pk__in=[first.pk, second.pk]).exists()
    assert "Deleted SemanticQueryRun rows: 1" in stdout


@pytest.mark.django_db
def test_output_counts_base_rows_not_total_collector_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_run(created_at=NOW - timedelta(hours=2))
    original_delete = QuerySet.delete

    def delete_with_related_count(queryset):
        total, details = original_delete(queryset)
        details["host.RelatedAuditObject"] = 7
        return total + 7, details

    monkeypatch.setattr(QuerySet, "delete", delete_with_related_count)

    stdout, _ = _call_purge("--before", VALID_BEFORE, "--execute")

    assert "Deleted SemanticQueryRun rows: 1" in stdout
    assert "Deleted SemanticQueryRun rows: 8" not in stdout


@pytest.mark.django_db
def test_initial_high_water_excludes_later_higher_primary_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial = _create_run(
        pk=87_650_000,
        created_at=NOW - timedelta(hours=2),
        question="initial-high-water-question",
    )
    inserted: dict[str, SemanticQueryRun] = {}
    original_capture = purge_command.capture_purge_high_water

    def capture_then_insert(*, alias: str, before: datetime) -> int | None:
        high_water = original_capture(alias=alias, before=before)
        inserted["run"] = _create_run(
            using=alias,
            pk=87_650_001,
            created_at=NOW - timedelta(hours=2),
            question="later-high-water-question",
        )
        return high_water

    monkeypatch.setattr(
        purge_command,
        "capture_purge_high_water",
        capture_then_insert,
    )

    stdout, stderr = _call_purge("--before", VALID_BEFORE, "--execute")

    assert not SemanticQueryRun.objects.filter(pk=initial.pk).exists()
    assert SemanticQueryRun.objects.filter(pk=inserted["run"].pk).exists()
    combined = f"{stdout}\n{stderr}"
    assert str(initial.pk) not in combined
    assert str(inserted["run"].pk) not in combined
    assert "high-water" not in combined.lower()
    assert "Deleted SemanticQueryRun rows: 1" in stdout


@pytest.mark.django_db(
    databases={"default", "asklens_read"},
    transaction=True,
)
def test_purge_preserves_selected_alias_for_all_queries() -> None:
    old = _create_run(
        using="asklens_read",
        created_at=NOW - timedelta(hours=2),
        question="purge-alias-question",
    )

    with CaptureQueriesContext(connections["default"]) as default_queries:
        with CaptureQueriesContext(connections["asklens_read"]) as alias_queries:
            stdout, _ = _call_purge(
                "--before",
                VALID_BEFORE,
                "--database",
                "asklens_read",
                "--execute",
            )

    assert not SemanticQueryRun.objects.using("asklens_read").filter(pk=old.pk).exists()
    assert default_queries.captured_queries == []
    assert alias_queries.captured_queries
    assert "Database alias: asklens_read" in stdout


@pytest.mark.django_db
def test_output_excludes_content_principal_error_pk_and_sql() -> None:
    user_sentinel = "unique-purge-user-sentinel"
    question_sentinel = "unique-purge-question-sentinel"
    plan_key_sentinel = "unique-purge-plan-key-sentinel"
    plan_value_sentinel = "unique-purge-plan-value-sentinel"
    error_sentinel = "unique-purge-error-sentinel"
    user = get_user_model().objects.create(username=user_sentinel)
    run = _create_run(
        pk=87_654_321,
        created_at=NOW - timedelta(hours=2),
        question=question_sentinel,
        plan={plan_key_sentinel: plan_value_sentinel},
        error=error_sentinel,
        user=user,
    )

    stdout, stderr = _call_purge(
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
    assert "DELETE FROM" not in combined.upper()


@pytest.mark.django_db
def test_custom_audit_mode_trap_sink_is_not_invoked(settings) -> None:
    events: list[object] = []

    def trap_sink(event: object) -> None:
        events.append(event)
        raise AssertionError("custom sink must not be invoked")

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "custom",
        "AUDIT_SINK": trap_sink,
        "AUDIT_INCLUDE_CONTENT": True,
    }
    old = _create_run(created_at=NOW - timedelta(hours=2))

    _call_purge("--before", VALID_BEFORE, "--execute")

    assert not SemanticQueryRun.objects.filter(pk=old.pk).exists()
    assert events == []


@pytest.mark.django_db
def test_normal_pre_delete_and_post_delete_signals_fire() -> None:
    old = _create_run(created_at=NOW - timedelta(hours=2))
    events: list[tuple[str, int, str]] = []

    def record_pre_delete(sender, instance, using, **kwargs) -> None:
        events.append(("pre", instance.pk, using))

    def record_post_delete(sender, instance, using, **kwargs) -> None:
        events.append(("post", instance.pk, using))

    pre_delete.connect(
        record_pre_delete,
        sender=SemanticQueryRun,
        weak=False,
        dispatch_uid="asklens-purge-test-pre",
    )
    post_delete.connect(
        record_post_delete,
        sender=SemanticQueryRun,
        weak=False,
        dispatch_uid="asklens-purge-test-post",
    )
    try:
        _call_purge("--before", VALID_BEFORE, "--execute")
    finally:
        pre_delete.disconnect(
            sender=SemanticQueryRun,
            dispatch_uid="asklens-purge-test-pre",
        )
        post_delete.disconnect(
            sender=SemanticQueryRun,
            dispatch_uid="asklens-purge-test-post",
        )

    assert events == [("pre", old.pk, "default"), ("post", old.pk, "default")]


@pytest.mark.django_db
def test_raising_host_signal_is_safe_and_rolls_back_database_batch() -> None:
    private_exception = "unique-private-host-signal-exception"
    old = _create_run(
        pk=87_654_322,
        created_at=NOW - timedelta(hours=2),
    )
    external_side_effects: list[int] = []

    def fail_after_delete(sender, instance, **kwargs) -> None:
        external_side_effects.append(instance.pk)
        raise RuntimeError(private_exception)

    post_delete.connect(
        fail_after_delete,
        sender=SemanticQueryRun,
        weak=False,
        dispatch_uid="asklens-purge-test-failing-post",
    )
    stdout = StringIO()
    stderr = StringIO()
    try:
        with pytest.raises(CommandError) as error:
            call_command(
                "purge_asklens_audit",
                "--before",
                VALID_BEFORE,
                "--execute",
                stdout=stdout,
                stderr=stderr,
                no_color=True,
            )
    finally:
        post_delete.disconnect(
            sender=SemanticQueryRun,
            dispatch_uid="asklens-purge-test-failing-post",
        )

    assert SemanticQueryRun.objects.filter(pk=old.pk).exists()
    assert external_side_effects == [old.pk]
    assert str(error.value) == "AskLens audit purge could not be completed."
    combined = f"{error.value}\n{stdout.getvalue()}\n{stderr.getvalue()}"
    assert private_exception not in combined
    assert str(old.pk) not in combined


@pytest.mark.django_db
def test_later_signal_failure_preserves_earlier_committed_batch_deletion() -> None:
    private_exception = "unique-private-later-batch-signal-exception"
    first = _create_run(
        pk=87_654_330,
        created_at=NOW - timedelta(hours=2),
    )
    second = _create_run(
        pk=87_654_331,
        created_at=NOW - timedelta(hours=2),
    )
    external_side_effects: list[int] = []

    def fail_on_second(sender, instance, **kwargs) -> None:
        external_side_effects.append(instance.pk)
        if instance.pk == second.pk:
            raise RuntimeError(private_exception)

    post_delete.connect(
        fail_on_second,
        sender=SemanticQueryRun,
        weak=False,
        dispatch_uid="asklens-purge-test-later-failing-post",
    )
    stdout = StringIO()
    stderr = StringIO()
    try:
        with pytest.raises(CommandError) as error:
            call_command(
                "purge_asklens_audit",
                "--before",
                VALID_BEFORE,
                "--batch-size",
                "1",
                "--execute",
                stdout=stdout,
                stderr=stderr,
                no_color=True,
            )
    finally:
        post_delete.disconnect(
            sender=SemanticQueryRun,
            dispatch_uid="asklens-purge-test-later-failing-post",
        )

    assert not SemanticQueryRun.objects.filter(pk=first.pk).exists()
    assert SemanticQueryRun.objects.filter(pk=second.pk).exists()
    assert external_side_effects == [first.pk, second.pk]
    assert str(error.value) == "AskLens audit purge could not be completed."
    combined = f"{error.value}\n{stdout.getvalue()}\n{stderr.getvalue()}"
    assert private_exception not in combined
    assert str(first.pk) not in combined
    assert str(second.pk) not in combined
    assert "Earlier completed batches can remain deleted" in stdout.getvalue()


@pytest.mark.django_db
def test_host_signal_base_exception_is_not_converted_to_command_error() -> None:
    old = _create_run(created_at=NOW - timedelta(hours=2))

    def interrupt_delete(sender, instance, **kwargs) -> None:
        raise KeyboardInterrupt

    pre_delete.connect(
        interrupt_delete,
        sender=SemanticQueryRun,
        weak=False,
        dispatch_uid="asklens-purge-test-interrupt-pre",
    )
    try:
        with pytest.raises(KeyboardInterrupt):
            _call_purge("--before", VALID_BEFORE, "--execute")
    finally:
        pre_delete.disconnect(
            sender=SemanticQueryRun,
            dispatch_uid="asklens-purge-test-interrupt-pre",
        )

    assert SemanticQueryRun.objects.filter(pk=old.pk).exists()
