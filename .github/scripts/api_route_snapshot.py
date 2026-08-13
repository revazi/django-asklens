"""Create and compare deterministic snapshots of the four AskLens API routes."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

_PRIVATE_BINDING = "private_category_storage"
_PRIVATE_TABLE = "api6_snapshot_record"
_SYNTHETIC_SECRET = "django-asklens-api6-synthetic-secret"
_DYNAMIC_VALUE = "<validated-dynamic-value>"


def _configure_django() -> None:
    """Configure one disposable in-memory Django application."""

    import django
    from django.conf import settings
    from django.core.management import call_command

    settings.configure(
        SECRET_KEY=_SYNTHETIC_SECRET,
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "rest_framework",
            "django_asklens",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        MIDDLEWARE=[],
        ROOT_URLCONF="django_asklens.api.urls",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
        DJANGO_ASKLENS={
            "AUDIT_INCLUDE_CONTENT": False,
            "LLM_BACKEND": "dummy",
        },
    )
    django.setup()
    call_command("migrate", interactive=False, verbosity=0)


def _assert_provenance(provenance: str, source_root: Path) -> None:
    """Prove whether imports came from source or the isolated wheel environment."""

    import django
    import rest_framework

    import django_asklens

    source_root = source_root.resolve()
    package_file = Path(django_asklens.__file__).resolve()
    source_package = source_root / "django_asklens"
    distribution_version = importlib.metadata.version("django-asklens")

    assert distribution_version == django_asklens.__version__
    if provenance == "source":
        assert package_file.is_relative_to(source_package), (
            f"Source probe imported outside {source_package}: {package_file}"
        )
    else:
        environment_root = Path(sys.prefix).resolve()
        assert package_file.is_relative_to(environment_root), (
            f"Wheel probe imported outside {environment_root}: {package_file}"
        )
        assert not package_file.is_relative_to(source_root), (
            f"Repository source shadowed the installed wheel: {package_file}"
        )
        shadowing_entries = []
        for entry in sys.path:
            entry_path = Path(entry).resolve() if entry else Path.cwd().resolve()
            if entry_path == source_root:
                shadowing_entries.append(entry)
        assert not shadowing_entries, (
            f"Repository root can shadow the installed wheel: {shadowing_entries}"
        )

    print(
        f"PASS {provenance} provenance: django-asklens {distribution_version}, "
        f"Django {django.get_version()}, DRF {rest_framework.VERSION} "
        f"from {package_file}"
    )


def _capture_response(response: Any) -> dict[str, Any]:
    """Capture status, every rendered header, and the parsed JSON body."""

    assert response["Content-Type"] == "application/json"
    return {
        "status": response.status_code,
        "headers": dict(response.items()),
        "body": json.loads(response.content.decode("utf-8")),
    }


def _assert_nonnegative_integer(value: Any, *, label: str) -> None:
    """Validate one duration before replacing its inherently variable value."""

    assert type(value) is int and value >= 0, f"Invalid {label}: {value!r}"


def _assert_positive_integer(value: Any, *, label: str) -> None:
    """Validate one generated identifier before replacing its value."""

    assert type(value) is int and value > 0, f"Invalid {label}: {value!r}"


def _assert_aware_timestamp(value: Any, *, label: str) -> None:
    """Validate one generated timestamp before replacing its value."""

    assert isinstance(value, str), f"Invalid {label}: {value!r}"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None and parsed.utcoffset() is not None, (
        f"Timestamp is not timezone-aware: {value!r}"
    )


def _assert_exact_keys(
    value: dict[str, Any], expected: set[str], *, label: str
) -> None:
    """Assert one response object has no missing or extra members."""

    assert set(value) == expected, f"Unexpected {label} keys: {set(value)!r}"


def _build_snapshot(source_root: Path) -> dict[str, Any]:
    """Exercise all routes with repository-owned synthetic data."""

    from django.contrib.auth import get_user_model
    from django.db import connection, models
    from rest_framework.test import APIClient

    from django_asklens import Metric
    from django_asklens.catalog.registry import default_registry
    from django_asklens.models import SemanticQueryRun

    class SyntheticRouteRecord(models.Model):
        private_category_storage = models.CharField(max_length=40)

        class Meta:
            app_label = "api6_snapshot"
            db_table = _PRIVATE_TABLE

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(SyntheticRouteRecord)

    user = get_user_model().objects.create(username="api6-synthetic-user")
    default_registry.clear()
    default_registry.register(
        model=SyntheticRouteRecord,
        name="synthetic_records",
        label="Synthetic Records",
        description="Repository-owned empty records for API parity evidence.",
        timezone="UTC",
        scope_mode="global",
        fields={
            "category": {
                "binding": _PRIVATE_BINDING,
                "type": "string",
                "nullable": False,
            }
        },
        metrics=[
            Metric(
                "record_count",
                op="count",
                binding="id",
                result_type="integer",
            )
        ],
    )

    client = APIClient()
    client.force_authenticate(user=user)
    catalog = _capture_response(client.get("/asklens/catalog/"))
    capabilities = _capture_response(client.get("/asklens/capabilities/"))
    query_success = _capture_response(
        client.post(
            "/asklens/query/",
            {
                "question": "Count synthetic records by category",
                "plan": {
                    "resource": "synthetic_records",
                    "intent": "aggregate",
                    "group_by": [{"field": "category"}],
                    "metrics": [{"metric": "record_count"}],
                    "limit": 10,
                },
                "presentation": {"kind": "table"},
            },
            format="json",
        )
    )
    query_capabilities_help = _capture_response(
        client.post(
            "/asklens/query/",
            {"question": "What can I query?"},
            format="json",
        )
    )

    query_body = query_success["body"]
    run_id = query_body["run_id"]
    _assert_positive_integer(run_id, label="query run_id")
    run_detail = _capture_response(client.get(f"/asklens/runs/{run_id}/"))
    run_body = run_detail["body"]
    result = query_body["result"]
    help_body = query_capabilities_help["body"]

    for label, response in (
        ("catalog", catalog),
        ("capabilities", capabilities),
        ("query success", query_success),
        ("query capabilities/help", query_capabilities_help),
        ("run detail", run_detail),
    ):
        assert response["status"] == 200, f"Unexpected {label} status: {response}"

    _assert_exact_keys(catalog["body"], {"resources"}, label="catalog")
    _assert_exact_keys(
        capabilities["body"],
        {
            "intents",
            "filter_logic",
            "types",
            "time_grains",
            "limits",
            "features",
            "aggregate_policies",
            "backend_restrictions",
        },
        label="capabilities",
    )
    _assert_exact_keys(
        query_body,
        {
            "question",
            "response_type",
            "plan",
            "result",
            "explanation",
            "run_id",
            "presentation",
        },
        label="query success",
    )
    _assert_exact_keys(
        result,
        {
            "columns",
            "data",
            "row_count",
            "empty",
            "duration_ms",
            "result_metadata",
        },
        label="complete result document",
    )
    assert result["empty"] is True
    assert result["data"] == []
    assert result["row_count"] == 0
    assert query_body["response_type"] == "query"
    _assert_exact_keys(
        help_body,
        {
            "question",
            "response_type",
            "routing",
            "capabilities",
            "catalog",
            "help",
            "explanation",
        },
        label="capabilities/help composition",
    )
    assert help_body["response_type"] == "capabilities"
    _assert_exact_keys(help_body["routing"], {"intent", "source"}, label="routing")
    _assert_exact_keys(help_body["help"], {"source", "content"}, label="help")
    assert help_body["help"]["source"] == "deterministic"
    assert help_body["help"]["content"]["suggestions"]
    assert help_body["capabilities"] == capabilities["body"]
    assert help_body["catalog"] == catalog["body"]

    _assert_exact_keys(
        run_body,
        {
            "id",
            "question",
            "plan",
            "status",
            "row_count",
            "duration_ms",
            "error",
            "created_at",
        },
        label="run detail",
    )
    assert run_body["id"] == run_id
    assert run_body["question"] == ""
    assert run_body["plan"] == {
        "resource": "synthetic_records",
        "intent": "aggregate",
    }
    assert run_body["status"] == "success"
    assert run_body["row_count"] == 0
    assert run_body["error"] is None
    assert SemanticQueryRun.objects.get(pk=run_id).user_id == user.pk
    assert SemanticQueryRun.objects.count() == 1

    _assert_nonnegative_integer(result["duration_ms"], label="result duration")
    _assert_nonnegative_integer(run_body["duration_ms"], label="run duration")
    assert run_body["duration_ms"] == result["duration_ms"]
    _assert_aware_timestamp(run_body["created_at"], label="run created_at")

    normalized_query = deepcopy(query_success)
    normalized_run = deepcopy(run_detail)
    normalized_query["body"]["run_id"] = _DYNAMIC_VALUE
    normalized_query["body"]["result"]["duration_ms"] = _DYNAMIC_VALUE
    normalized_run["body"]["id"] = _DYNAMIC_VALUE
    normalized_run["body"]["duration_ms"] = _DYNAMIC_VALUE
    normalized_run["body"]["created_at"] = _DYNAMIC_VALUE

    snapshot = {
        "snapshot_format": "django-asklens-api-routes-v1",
        "interactions": {
            "catalog": {
                "route": "GET /asklens/catalog/",
                "response": catalog,
            },
            "capabilities": {
                "route": "GET /asklens/capabilities/",
                "response": capabilities,
            },
            "query_success": {
                "route": "POST /asklens/query/",
                "response": normalized_query,
            },
            "query_capabilities_help": {
                "route": "POST /asklens/query/",
                "response": query_capabilities_help,
            },
            "run_detail": {
                "route": "GET /asklens/runs/<int:pk>/",
                "response": normalized_run,
            },
        },
    }
    serialized = json.dumps(snapshot, sort_keys=True)
    forbidden_values = (
        _PRIVATE_BINDING,
        _PRIVATE_TABLE,
        _SYNTHETIC_SECRET,
        ":memory:",
        "api6_snapshot",
        "tenant_id",
        "scope_token",
        str(source_root.resolve()),
    )
    for forbidden in forbidden_values:
        assert forbidden not in serialized, (
            f"Private value leaked into snapshot: {forbidden}"
        )
    return snapshot


def _write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    """Write one canonical UTF-8 JSON snapshot."""

    output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    print(f"PASS wrote deterministic API route snapshot: {output}")


def _compare_snapshots(expected_path: Path, actual_path: Path) -> None:
    """Compare canonical bytes and parsed structures for useful failure evidence."""

    expected_bytes = expected_path.read_bytes()
    actual_bytes = actual_path.read_bytes()
    expected = json.loads(expected_bytes)
    actual = json.loads(actual_bytes)
    assert actual == expected, "Installed-wheel API route structure differs from source"
    assert actual_bytes == expected_bytes, (
        "Installed-wheel API route snapshot bytes differ from canonical source bytes"
    )
    print("PASS installed-wheel API routes exactly match the source snapshot")


def main() -> None:
    """Run a source/wheel probe or compare two completed snapshots."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provenance", choices=("source", "wheel"))
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("SOURCE_SNAPSHOT", "WHEEL_SNAPSHOT"),
        type=Path,
    )
    args = parser.parse_args()

    if args.compare is not None:
        probe_arguments = (args.provenance, args.source_root, args.output)
        if any(value is not None for value in probe_arguments):
            parser.error("--compare cannot be combined with probe arguments")
        _compare_snapshots(*args.compare)
        return
    if args.provenance is None or args.source_root is None or args.output is None:
        parser.error("--provenance, --source-root, and --output are required")

    _configure_django()
    _assert_provenance(args.provenance, args.source_root)
    snapshot = _build_snapshot(args.source_root)
    _write_snapshot(snapshot, args.output)


if __name__ == "__main__":
    main()
