"""Replay the language-neutral AskLens conformance corpus."""

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from pydantic import ValidationError

from django_asklens.catalog.capabilities import build_capabilities
from django_asklens.contracts._generation import validate_contract_document
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import execute_plan
from django_asklens.permissions import get_request_permissions
from tests.conformance.support import (
    CONFORMANCE_NOW,
    SCENARIOS,
    build_registry,
    build_request,
    configure_settings,
    create_synthetic_rows,
)

CONFORMANCE_ROOT = Path(__file__).resolve().parents[2] / "conformance"
EXPECTED_CATEGORIES = {
    "budget",
    "member-scope-security",
    "ordering-truncation",
    "positive",
    "semantic",
    "serialization",
    "structural-negative",
}
pytestmark = pytest.mark.postgresql

FORBIDDEN_FIXTURE_PROPERTIES = {
    "binding",
    "clock",
    "now",
    "permissions",
    "queryset",
    "requires_permission",
    "scope_provider",
    "tenant_id",
}


def _load_cases() -> list[tuple[Path, dict[str, Any]]]:
    cases: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(CONFORMANCE_ROOT.glob("*/*.json")):
        cases.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return cases


CASES = _load_cases()


@pytest.mark.postgresql
def test_postgresql_backend_and_server_major() -> None:
    """Fail a required PostgreSQL run that targets the wrong database."""

    expected_major = os.environ.get("DJANGO_ASKLENS_POSTGRES_EXPECTED_MAJOR")
    if expected_major is None:
        pytest.skip("PostgreSQL server-major guard is only required in PostgreSQL runs")

    assert expected_major in {"15", "18"}
    assert connection.vendor == "postgresql"
    assert connection.pg_version // 10_000 == int(expected_major)


def _property_names(value: object) -> set[str]:
    names: set[str] = set()
    if isinstance(value, Mapping):
        names.update(str(name) for name in value)
        for child in value.values():
            names.update(_property_names(child))
    elif isinstance(value, list):
        for child in value:
            names.update(_property_names(child))
    return names


def test_required_conformance_categories_exist() -> None:
    categories = {path.parent.name for path, _case in CASES}

    assert categories == EXPECTED_CATEGORIES


def test_fixture_documents_are_language_neutral_and_schema_checked() -> None:
    seen_case_ids: set[str] = set()

    for path, case in CASES:
        raw_text = path.read_text(encoding="utf-8")
        assert "django" not in raw_text.lower()
        assert set(case) == {
            "capabilities",
            "case_id",
            "catalog",
            "category",
            "execution",
            "expected",
            "plan",
        }
        assert case["category"] == path.parent.name
        assert case["case_id"].startswith(f"{case['category']}.")
        assert case["case_id"] not in seen_case_ids
        seen_case_ids.add(case["case_id"])
        assert set(case["execution"]) == {"scenario"}
        assert case["execution"]["scenario"] in SCENARIOS
        assert FORBIDDEN_FIXTURE_PROPERTIES.isdisjoint(_property_names(case))
        assert isinstance(case["plan"], dict)

        expected = case["expected"]
        assert isinstance(expected.get("application_data_queries"), int)
        assert expected["application_data_queries"] >= 0
        assert ("result" in expected) != ("error" in expected)
        assert set(expected) in (
            {"application_data_queries", "result"},
            {"application_data_queries", "error"},
        )

        validate_contract_document("catalog", case["catalog"])
        validate_contract_document("capabilities", case["capabilities"])
        if case["category"] == "structural-negative":
            with pytest.raises(ValidationError):
                validate_contract_document("query-plan", case["plan"])
        else:
            validate_contract_document("query-plan", case["plan"])
        if "result" in expected:
            validate_contract_document("result", expected["result"])
        else:
            validate_contract_document("error", expected["error"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "case"),
    CASES,
    ids=[case["case_id"] for _path, case in CASES],
)
def test_django_replays_language_neutral_case(
    settings: Any,
    path: Path,
    case: dict[str, Any],
) -> None:
    """Replay fixture input through server-owned identity, policy, and scope."""

    del path
    scenario = SCENARIOS[case["execution"]["scenario"]]
    configure_settings(settings, scenario)
    accounts = create_synthetic_rows()
    registry = build_registry()
    request = build_request(scenario, accounts)
    permissions = get_request_permissions(request)

    assert permissions == scenario.permissions
    assert registry.to_dict(permissions=permissions) == case["catalog"]
    assert build_capabilities() == case["capabilities"]

    with CaptureQueriesContext(connection) as captured:
        try:
            with (
                patch(
                    "django_asklens.execution.runner.perf_counter",
                    side_effect=(10.0, 10.003),
                ),
                patch(
                    "django_asklens.execution.runner.timezone.now",
                    return_value=CONFORMANCE_NOW,
                ),
            ):
                result = execute_plan(case["plan"], request=request, registry=registry)
        except PublicAskLensError as exc:
            actual = {
                "application_data_queries": len(captured),
                "error": public_error_payload(exc),
            }
        else:
            actual = {
                "application_data_queries": len(captured),
                "result": result.to_dict(),
            }

    assert actual == case["expected"]
    if captured:
        assert all("test_project_order" in query["sql"] for query in captured)
