"""Deterministic synthetic hostile-payload evidence for the authenticated API.

This bounded stdlib-generated corpus exercises transport combinations only. It
is replayable evidence, not exhaustive fuzzing, an independent security audit,
or security certification. No live provider or network call is permitted.
"""

import json
import os
import random
from dataclasses import dataclass
from typing import Any, Literal

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from django_asklens.models import SemanticQueryRun
from tests.test_project.models import Order

DEFAULT_GENERATION_SEED = 20260819
MAX_GENERATED_CASES = 16
MAX_GENERATED_DEPTH = 6
MAX_SERIALIZED_PAYLOAD_BYTES = 4_096
APPLICATION_TABLE = "test_project_order"
AUDIT_TABLE = "asklens_semanticqueryrun"
QUESTION = "Synthetic SEC-4 transport evidence"
REQUEST_PARSE_ERROR = {
    "code": "asklens.parse.invalid",
    "message": "The AskLens request could not be parsed.",
}
PLAN_PARSE_ERROR = {
    "code": "asklens.parse.invalid",
    "message": "The query plan could not be parsed.",
}
PRESENTATION_PARSE_ERROR = {**PLAN_PARSE_ERROR, "pointer": "/presentation"}
MEMBER_UNAVAILABLE_ERROR = {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable.",
}


def _generation_seed() -> int:
    """Return the integer seed used for deterministic local replay."""

    raw_seed = os.getenv("ASKLENS_SEC4_GENERATION_SEED", str(DEFAULT_GENERATION_SEED))
    try:
        return int(raw_seed)
    except ValueError as exc:
        raise ValueError(
            "ASKLENS_SEC4_GENERATION_SEED must be an integer for deterministic replay."
        ) from exc


GENERATION_SEED = _generation_seed()


@dataclass(frozen=True)
class _GeneratedCase:
    """One bounded JSON request expected to fail at a named boundary."""

    case_id: str
    boundary: Literal["transport", "trusted"]
    payload: dict[str, Any]
    expected_error: dict[str, str]
    private_tokens: tuple[str, ...]


def _valid_plan() -> dict[str, Any]:
    """Return a valid supplied plan so generated cases combine HTTP fields."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"metric": "order_count"}],
        "limit": 10,
    }


def _valid_request() -> dict[str, Any]:
    """Return the shared JSON request before one hostile mutation."""

    return {
        "question": QUESTION,
        "plan": _valid_plan(),
        "presentation": {"kind": "table"},
    }


def _private_value(rng: random.Random, label: str) -> str:
    """Return a distinctive synthetic private/policy-like leak sentinel."""

    return f"sec4-private-{label}-{rng.randrange(10_000, 100_000)}"


def _nested_private_value(rng: random.Random, label: str) -> tuple[dict[str, Any], str]:
    """Return one small nested JSON value and its distinctive sentinel."""

    token = _private_value(rng, label)
    return {"claim": [{"marker": token}]}, token


def _build_generated_cases(seed: int) -> tuple[_GeneratedCase, ...]:
    """Build the fixed-count transport corpus from one replay seed."""

    rng = random.Random(seed)
    cases: list[_GeneratedCase] = []

    for label in ("tenant-scope", "permission-policy", "credential-claim"):
        payload = _valid_request()
        private_value, value_token = _nested_private_value(rng, label)
        private_key = f"sec4_{label.replace('-', '_')}_{rng.randrange(10_000, 100_000)}"
        payload[private_key] = private_value
        cases.append(
            _GeneratedCase(
                case_id=f"seed{seed}-transport-unknown-{label}",
                boundary="transport",
                payload=payload,
                expected_error=REQUEST_PARSE_ERROR,
                private_tokens=(private_key, value_token),
            )
        )

    for index, value_factory in enumerate(
        (
            lambda token: {"prompt": token},
            lambda token: [token],
        ),
        start=1,
    ):
        token = _private_value(rng, f"question-shape-{index}")
        payload = _valid_request()
        payload["question"] = value_factory(token)
        cases.append(
            _GeneratedCase(
                case_id=f"seed{seed}-transport-question-shape-{index}",
                boundary="transport",
                payload=payload,
                expected_error=REQUEST_PARSE_ERROR,
                private_tokens=(token,),
            )
        )

    for field in ("debug", "include_presentation"):
        token = _private_value(rng, f"{field}-policy")
        payload = _valid_request()
        payload[field] = {"claim": token}
        cases.append(
            _GeneratedCase(
                case_id=f"seed{seed}-transport-{field}-shape",
                boundary="transport",
                payload=payload,
                expected_error=REQUEST_PARSE_ERROR,
                private_tokens=(token,),
            )
        )

    plan_extra_token = _private_value(rng, "plan-tenant-binding")
    plan_extra_key = f"tenant_binding_{rng.randrange(10_000, 100_000)}"
    payload = _valid_request()
    payload["plan"][plan_extra_key] = {"value": plan_extra_token}
    cases.append(
        _GeneratedCase(
            case_id=f"seed{seed}-trusted-plan-extra",
            boundary="trusted",
            payload=payload,
            expected_error=PLAN_PARSE_ERROR,
            private_tokens=(plan_extra_key, plan_extra_token),
        )
    )

    metric_extra_token = _private_value(rng, "metric-private-operation")
    metric_extra_key = f"private_operation_{rng.randrange(10_000, 100_000)}"
    payload = _valid_request()
    payload["plan"]["metrics"][0][metric_extra_key] = metric_extra_token
    cases.append(
        _GeneratedCase(
            case_id=f"seed{seed}-trusted-metric-extra",
            boundary="trusted",
            payload=payload,
            expected_error=PLAN_PARSE_ERROR,
            private_tokens=(metric_extra_key, metric_extra_token),
        )
    )

    unavailable_resource = _private_value(rng, "tenant-resource")
    payload = _valid_request()
    payload["plan"]["resource"] = unavailable_resource
    cases.append(
        _GeneratedCase(
            case_id=f"seed{seed}-trusted-resource-unavailable",
            boundary="trusted",
            payload=payload,
            expected_error=MEMBER_UNAVAILABLE_ERROR,
            private_tokens=(unavailable_resource,),
        )
    )

    unavailable_field = _private_value(rng, "permission-field")
    payload = _valid_request()
    payload["plan"]["group_by"] = [{"field": unavailable_field}]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{seed}-trusted-field-unavailable",
            boundary="trusted",
            payload=payload,
            expected_error=MEMBER_UNAVAILABLE_ERROR,
            private_tokens=(unavailable_field,),
        )
    )

    presentation_extra_token = _private_value(rng, "presentation-scope")
    presentation_extra_key = f"scope_override_{rng.randrange(10_000, 100_000)}"
    payload = _valid_request()
    payload["presentation"] = {
        "kind": "table",
        presentation_extra_key: presentation_extra_token,
    }
    cases.append(
        _GeneratedCase(
            case_id=f"seed{seed}-trusted-presentation-extra",
            boundary="trusted",
            payload=payload,
            expected_error=PRESENTATION_PARSE_ERROR,
            private_tokens=(presentation_extra_key, presentation_extra_token),
        )
    )

    presentation_kind = _private_value(rng, "presentation-kind")
    payload = _valid_request()
    payload["presentation"] = {"kind": presentation_kind}
    cases.append(
        _GeneratedCase(
            case_id=f"seed{seed}-trusted-presentation-kind",
            boundary="trusted",
            payload=payload,
            expected_error=PRESENTATION_PARSE_ERROR,
            private_tokens=(presentation_kind,),
        )
    )

    presentation_axis = _private_value(rng, "presentation-axis")
    payload = _valid_request()
    payload["presentation"] = {"kind": "table", "x": presentation_axis}
    cases.append(
        _GeneratedCase(
            case_id=f"seed{seed}-trusted-presentation-axes",
            boundary="trusted",
            payload=payload,
            expected_error=PRESENTATION_PARSE_ERROR,
            private_tokens=(presentation_axis,),
        )
    )

    presentation_container = _private_value(rng, "presentation-container")
    payload = _valid_request()
    payload["presentation"] = [presentation_container]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{seed}-trusted-presentation-container",
            boundary="trusted",
            payload=payload,
            expected_error=PRESENTATION_PARSE_ERROR,
            private_tokens=(presentation_container,),
        )
    )

    return tuple(cases)


GENERATED_CASES = _build_generated_cases(GENERATION_SEED)
TRANSPORT_CASES = tuple(
    case for case in GENERATED_CASES if case.boundary == "transport"
)
TRUSTED_CASES = tuple(case for case in GENERATED_CASES if case.boundary == "trusted")


@pytest.fixture(autouse=True)
def isolate_registry() -> None:
    """Keep the generated transport catalog isolated from other tests."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Return a real authenticated DRF test transport."""

    user = get_user_model().objects.create_user(username="sec4-hostile-payload-user")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def registered_orders() -> None:
    """Register synthetic application data without creating any rows."""

    default_registry.register(
        model=Order,
        name="orders",
        label="Orders",
        timezone="UTC",
        scope_mode="global",
        fields={
            "status": {
                "binding": "status",
                "type": "string",
                "nullable": False,
            }
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
    )


def _json_depth(value: Any) -> int:
    """Return deterministic container depth for the bounded-corpus guard."""

    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _table_sql(queries: list[dict[str, str]], table: str) -> list[str]:
    """Return captured statements that target one named table."""

    return [query["sql"] for query in queries if table in query["sql"].lower()]


def _assert_safe_http_response(response, expected_error: dict[str, str]) -> str:
    """Assert the exact current error envelope and relevant response headers."""

    assert response.status_code == 400
    assert response["Content-Type"] == "application/json"
    assert response["Allow"] == "POST, OPTIONS"
    assert set(response.data) in ({"error"}, {"error", "run_id"})
    assert response.data["error"] == expected_error
    return json.dumps(response.data, sort_keys=True, separators=(",", ":"))


def _assert_tokens_absent(case: _GeneratedCase, *safe_surfaces: str) -> None:
    """Assert generated private/policy sentinels are not reflected or stored."""

    for token in case.private_tokens:
        assert token
        for surface in safe_surfaces:
            assert token not in surface


def test_generated_hostile_http_corpus_is_deterministic_json_and_bounded() -> None:
    """Pin replayability plus explicit count, depth, and serialized-size bounds."""

    assert GENERATED_CASES == _build_generated_cases(GENERATION_SEED)
    assert 0 < len(GENERATED_CASES) <= MAX_GENERATED_CASES
    assert len(TRANSPORT_CASES) >= 7
    assert len(TRUSTED_CASES) >= 8
    assert len({case.case_id for case in GENERATED_CASES}) == len(GENERATED_CASES)

    serialized_payloads: list[str] = []
    for case in GENERATED_CASES:
        serialized = json.dumps(
            case.payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        serialized_payloads.append(serialized)
        assert json.loads(serialized) == case.payload
        assert len(serialized.encode("utf-8")) <= MAX_SERIALIZED_PAYLOAD_BYTES
        assert _json_depth(case.payload) <= MAX_GENERATED_DEPTH
    assert len(set(serialized_payloads)) == len(GENERATED_CASES)


@pytest.mark.parametrize("case", TRANSPORT_CASES, ids=lambda case: case.case_id)
@pytest.mark.django_db
def test_generated_request_shape_denials_stop_before_orchestration_audit_and_sql(
    case: _GeneratedCase,
    api_client: APIClient,
    registered_orders: None,
    monkeypatch,
) -> None:
    """Serializer-level hostile combinations remain generic and unaudited."""

    def fail_orchestration(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Request-shape rejection must precede orchestration.")

    monkeypatch.setattr(
        "django_asklens.api.views.execute_asklens_query_request",
        fail_orchestration,
    )

    with CaptureQueriesContext(connection) as captured:
        response = api_client.post("/asklens/query/", case.payload, format="json")

    response_text = _assert_safe_http_response(response, case.expected_error)
    assert set(response.data) == {"error"}
    assert _table_sql(captured.captured_queries, APPLICATION_TABLE) == []
    assert _table_sql(captured.captured_queries, AUDIT_TABLE) == []
    assert SemanticQueryRun.objects.count() == 0
    _assert_tokens_absent(case, response_text)


@pytest.mark.parametrize("case", TRUSTED_CASES, ids=lambda case: case.case_id)
@pytest.mark.django_db
def test_generated_provided_plan_and_presentation_denials_are_safe_and_metadata_only(
    case: _GeneratedCase,
    api_client: APIClient,
    registered_orders: None,
    monkeypatch,
) -> None:
    """Trusted rejection avoids planners/data SQL and stores only safe metadata."""

    def fail_planning(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("A supplied plan must not reach a provider or planner.")

    monkeypatch.setattr("django_asklens.querying.plan_question", fail_planning)
    monkeypatch.setattr("django_asklens.querying.plan_asklens_response", fail_planning)
    monkeypatch.setattr("django_asklens.querying.route_question_intent", fail_planning)

    with CaptureQueriesContext(connection) as captured:
        response = api_client.post("/asklens/query/", case.payload, format="json")

    response_text = _assert_safe_http_response(response, case.expected_error)
    assert set(response.data) == {"error", "run_id"}
    assert isinstance(response.data["run_id"], int)
    assert _table_sql(captured.captured_queries, APPLICATION_TABLE) == []
    audit_sql = _table_sql(captured.captured_queries, AUDIT_TABLE)
    assert len(audit_sql) == 1
    assert audit_sql[0].lstrip().upper().startswith("INSERT")

    run = SemanticQueryRun.objects.get(pk=response.data["run_id"])
    assert run.question == ""
    assert run.plan == {}
    assert run.status == SemanticQueryRun.Status.FAILED
    assert run.row_count == 0
    assert run.duration_ms is None
    assert run.error == (
        f"{case.expected_error['code']}: {case.expected_error['message']}"
    )
    audit_text = json.dumps(
        {
            "question": run.question,
            "plan": run.plan,
            "status": run.status,
            "row_count": run.row_count,
            "duration_ms": run.duration_ms,
            "error": run.error,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    _assert_tokens_absent(case, response_text, audit_text)
