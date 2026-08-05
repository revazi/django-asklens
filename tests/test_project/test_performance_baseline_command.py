"""Tests for the synthetic performance baseline management command."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from tests.test_project.management.commands.run_performance_baseline import (
    Command,
    _collect_default_commit,
    _CountOnlyAuditSink,
    _database_server_version,
    _wall_duration_ms,
    summarize_numeric_series,
)

pytestmark = pytest.mark.django_db

FORBIDDEN_KEYS = {
    "user",
    "principal",
    "permission",
    "permissions",
    "credential",
    "host",
    "port",
    "env",
    "question",
    "plan",
    "filter",
    "sql",
    "row",
    "value",
    "binding",
    "model",
    "provider",
    "content",
    "api_key",
    "password",
    "secret",
    "tenant_id",
}

TOP_LEVEL_KEYS_WITH_COMMIT = {
    "evidence_kind",
    "status",
    "synthetic",
    "generated_at",
    "environment",
    "dataset",
    "run_config",
    "cases",
    "limitations",
    "commit",
}
TOP_LEVEL_KEYS = TOP_LEVEL_KEYS_WITH_COMMIT

TOP_LEVEL_CASE_KEYS = {
    "name",
    "resource",
    "intent",
    "status",
    "samples",
    "duration_ms",
    "wall_duration_ms",
    "query_count",
    "row_count",
    "result_metadata",
    "audit",
}

FORBIDDEN_TEXT_SNIPPETS = {
    "north studio",
    "south studio",
    "north-studio",
    "south-studio",
    "northstudio",
    "southstudio",
    "north_owner",
    "south_owner",
    "demo admin",
    "created_at",
    "alex",
    "blair",
    "performance baseline",
    "asklens",
    "12admin34",
    "north-owner",
    "south-owner",
    "facilityowner",
    "analyticsview",
    "billingreportsview",
}


def _assert_no_forbidden_keys(payload: object) -> None:
    """Reject raw rows, SQL/prov payloads, and credentials in artifact output."""

    if isinstance(payload, dict):
        for key, value in payload.items():
            assert key.lower() not in FORBIDDEN_KEYS
            _assert_no_forbidden_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_forbidden_keys(item)


def _read_commit_from_repo() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _expected_profile_payload(artifact: Path) -> dict:
    call_command(
        "seed_complex_test_project",
        size="small",
        verbosity=0,
    )
    call_command(
        "run_performance_baseline",
        user="admin",
        dataset_profile="small",
        query_profile="compact",
        iterations=2,
        warmups=0,
        output=artifact,
        verbosity=0,
    )
    return json.loads(artifact.read_text(encoding="utf-8"))


@pytest.mark.django_db
def test_run_performance_baseline_emits_redacted_payload_and_schema(
    tmp_path: Path,
) -> None:
    """The command emits fixed corpus JSON and omits disallowed fields."""

    artifact = tmp_path / "artifacts" / "baseline.json"
    payload = _expected_profile_payload(artifact)

    assert payload["evidence_kind"] == "synthetic_query_performance"
    assert payload["status"] == "success"
    assert payload["synthetic"] is True
    assert payload["commit"] == _read_commit_from_repo()
    assert payload["run_config"]["query_profile"] == "compact"
    assert payload["run_config"]["dataset_profile"] == "small"
    assert payload["run_config"]["iterations"] == {"measured": 2, "warmups": 0}
    assert payload["run_config"]["audit_mode"] == "custom_metadata_discard"

    environment = payload["environment"]
    assert environment["database_vendor"] in {"sqlite", "postgresql"}

    case = payload["cases"][0]
    assert case["name"] == "member-directory-truncated"
    assert case["resource"] == "members"
    assert case["intent"] == "list"
    assert case["status"] == "success"
    assert set(case.keys()) == TOP_LEVEL_CASE_KEYS
    assert set(payload.keys()) == TOP_LEVEL_KEYS

    expected_case_metadata = {
        "limit": 3,
        "limit_scope": "rows",
        "truncated": True,
    }
    assert case["result_metadata"] == expected_case_metadata
    assert case["audit"]["mode"] == "custom_metadata_discard"
    assert case["audit"]["event_count"] == 2

    samples = case["samples"]
    assert len(samples) == 2
    for sample in samples:
        assert set(sample) == {
            "duration_ms",
            "wall_duration_ms",
            "query_count",
            "row_count",
        }
        assert sample["duration_ms"] >= 0
        assert isinstance(sample["wall_duration_ms"], float)
        assert sample["wall_duration_ms"] >= 0.0
        assert sample["query_count"] >= 1

    assert case["result_metadata"] == expected_case_metadata

    for summary in (
        case["duration_ms"],
        case["wall_duration_ms"],
        case["query_count"],
        case["row_count"],
    ):
        assert summary["count"] == 2
        assert summary["min"] <= summary["p50"] <= summary["p95"] <= summary["max"]
        assert summary["min"] >= 0
        assert summary["max"] >= summary["min"]

    payload_text = artifact.read_text(encoding="utf-8")
    lowered = payload_text.lower()
    assert "plan" not in lowered
    for snippet in FORBIDDEN_TEXT_SNIPPETS:
        assert snippet not in lowered

    _assert_no_forbidden_keys(payload)


def test_run_performance_baseline_parser_accepts_legacy_dataset_profile_alias() -> None:
    """Legacy --size alias maps to dataset_profile in argument parsing."""

    parser = Command().create_parser("manage", "run_performance_baseline")
    parsed = parser.parse_args(["--size", "small", "--query-profile", "compact"])
    assert parsed.dataset_profile == "small"


def test_run_performance_baseline_rejects_invalid_dataset_profile() -> None:
    """Dataset profile choices are validated at parse/command boundaries."""

    parser = Command().create_parser("manage", "run_performance_baseline")
    with pytest.raises(CommandError):
        parser.parse_args(["--dataset-profile", "not-a-profile"])


def test_run_performance_baseline_rejects_invalid_query_profile() -> None:
    """Query profile choices are bounded and parser validated."""

    parser = Command().create_parser("manage", "run_performance_baseline")
    with pytest.raises(CommandError):
        parser.parse_args(["--query-profile", "not-a-profile"])


def test_run_performance_baseline_rejects_invalid_artifact_name() -> None:
    """Artifact names are bounded and filesystem-safe."""

    with pytest.raises(CommandError):
        call_command(
            "run_performance_baseline",
            user="admin",
            artifact_name="bad/name",
            iterations=1,
            warmups=0,
            dataset_profile="small",
            query_profile="compact",
        )


def test_run_performance_baseline_rejects_empty_output_path() -> None:
    """Empty output path is rejected early."""

    with pytest.raises(CommandError):
        call_command(
            "run_performance_baseline",
            user="admin",
            output="",
            iterations=1,
            warmups=0,
        )


@pytest.mark.django_db
def test_run_performance_baseline_supports_explicit_commit_and_schema(
    tmp_path: Path,
) -> None:
    """Explicit commit overrides default and preserves closed artifact schema."""

    artifact = tmp_path / "artifacts" / "baseline-commit.json"
    commit = "0" * 40

    call_command(
        "seed_complex_test_project",
        size="small",
        verbosity=0,
    )
    call_command(
        "run_performance_baseline",
        user="admin",
        dataset_profile="small",
        query_profile="compact",
        iterations=1,
        warmups=0,
        commit=commit,
        output=artifact,
        verbosity=0,
    )

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["commit"] == commit
    assert set(payload.keys()) == TOP_LEVEL_KEYS

    # Warmups must not contribute to measured event counts.
    artifact_with_warmups = tmp_path / "artifacts" / "baseline-warmups.json"
    call_command(
        "run_performance_baseline",
        user="admin",
        dataset_profile="small",
        query_profile="compact",
        iterations=2,
        warmups=1,
        output=artifact_with_warmups,
        verbosity=0,
    )
    payload_with_warmups = json.loads(artifact_with_warmups.read_text(encoding="utf-8"))
    assert payload_with_warmups["cases"][0]["audit"]["event_count"] == 2


def test_count_only_audit_sink_keeps_metrics_and_rejects_privacy_leaks() -> None:
    """Metadata-only sink counts events and retains no content payload."""

    sink = _CountOnlyAuditSink()
    assert not hasattr(sink, "__dict__")

    sink({"question": "", "plan": {}})
    sink({"question": None, "plan": []})
    assert sink.count() == 2

    with pytest.raises(ValueError, match="question"):
        sink({"question": "Performance baseline: x"})
    with pytest.raises(ValueError, match="plan"):
        sink({"plan": {"resource": "members", "intent": "list"}})
    with pytest.raises(ValueError, match="plan"):
        sink({"plan": 1})
    with pytest.raises(ValueError, match="question"):
        sink({"question": "".join(["Performance", " baseline", " leak"])})


@pytest.mark.django_db
def test_run_performance_baseline_requires_seeded_user(tmp_path: Path) -> None:
    """The baseline runner rejects unknown identities quickly."""

    artifact = tmp_path / "missing.json"

    with pytest.raises(CommandError, match="Demo user 'ghost' does not exist"):
        call_command(
            "run_performance_baseline",
            user="ghost",
            query_profile="compact",
            iterations=1,
            warmups=0,
            output=artifact,
            verbosity=0,
        )


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "101", "abc", ""],
)
def test_run_performance_baseline_rejects_invalid_iterations(value: str) -> None:
    """Iterations stay bounded and are validated as positive integers."""

    with pytest.raises(CommandError):
        call_command(
            "run_performance_baseline",
            user="admin",
            query_profile="compact",
            iterations=value,
            warmups=0,
        )


@pytest.mark.parametrize(
    "value",
    ["-1", "21", "abc", ""],
)
def test_run_performance_baseline_rejects_invalid_warmups(value: str) -> None:
    """Warmups stay bounded including explicit upper bound checks."""

    with pytest.raises(CommandError):
        call_command(
            "run_performance_baseline",
            user="admin",
            query_profile="compact",
            iterations=1,
            warmups=value,
        )


@pytest.mark.parametrize(
    "value",
    ["1234", "0" * 10, "G" * 40],
)
def test_run_performance_baseline_rejects_invalid_commit(value: str) -> None:
    """Commit SHA must be full lowercase hex."""

    with pytest.raises(CommandError):
        call_command(
            "run_performance_baseline",
            query_profile="compact",
            commit=value,
            iterations=1,
            warmups=0,
        )


def test_collect_default_commit_derives_current_head() -> None:
    """Default commit is resolved from current checkout by default."""

    assert _collect_default_commit() == _read_commit_from_repo()


def test_collect_default_commit_rejects_non_hex_commit(monkeypatch) -> None:
    """Hard-fail if current HEAD is not a valid commit string."""

    module_name = "tests.test_project.management.commands.run_performance_baseline"
    from importlib import import_module

    module = import_module(module_name)
    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda *args, **kwargs: "NOT_A_SHA\n",
    )
    with pytest.raises(CommandError):
        module._collect_default_commit()


def test_summarize_numeric_series_prefers_nearest_rank_percentiles() -> None:
    """Summaries compute nearest-rank p50 and p95 deterministically."""

    summary = summarize_numeric_series([9, 10, 3, 7, 12])

    assert summary == {
        "count": 5,
        "min": 3,
        "max": 12,
        "p50": 9,
        "p95": 12,
        "mean": 8.2,
    }

    assert summary == summarize_numeric_series([3, 7, 9, 10, 12])

    with pytest.raises(CommandError):
        summarize_numeric_series([])


def test_wall_duration_ms_preserves_3_decimal_precision() -> None:
    """Wall duration helper rounds wall time to 3 decimals."""

    assert _wall_duration_ms(1_234_000, 2_468_000) == 1.234


def test_database_server_version_formats_postgresql_minor_component() -> None:
    """PostgreSQL int parsing extracts major and full minor from server_version."""

    import types

    import tests.test_project.management.commands.run_performance_baseline as module

    original_connection = module.connection
    module.connection = types.SimpleNamespace(
        connection=types.SimpleNamespace(
            info=types.SimpleNamespace(server_version=180004)
        ),
        vendor="postgresql",
    )
    try:
        assert _database_server_version(vendor="postgresql") == "18.4"
    finally:
        module.connection = original_connection


def test_database_server_version_preserves_sqlite_version() -> None:
    """SQLite fallback preserves python-level driver version."""

    version = _database_server_version(vendor="sqlite")
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", version)
