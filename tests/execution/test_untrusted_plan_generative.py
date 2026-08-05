"""Deterministic stdlib-generated untrusted-plan boundary tests.

These tests provide synthetic safety evidence only and intentionally avoid
changing production runtime behavior.
"""

import copy
import json
import os
import random
import traceback
from dataclasses import dataclass

import pytest

from django_asklens.exceptions import (
    PlanParseError,
    PublicAskLensError,
    normalize_public_error,
    public_error_payload,
)
from django_asklens.execution import execute_plan
from django_asklens.planning import QueryPlan, parse_query_plan
from tests.execution.test_facade import build_registry, request_with, status_plan


def _generation_seed() -> int:
    """Read deterministic seed from test environment (default documented)."""

    return int(os.getenv("ASKLENS_HARDENING_GENERATION_SEED", "20260805"))


GENERATION_SEED = _generation_seed()

EXPECTED_PUBLIC_MESSAGES = {
    "asklens.parse.invalid": "The query plan could not be parsed.",
    "asklens.member.unavailable": "A requested query member is unavailable.",
    "asklens.plan.invalid": "The query plan is invalid.",
    "asklens.budget.exceeded": "The query plan exceeds an execution limit.",
}


@dataclass(frozen=True)
class _GeneratedCase:
    """One bounded synthetic failure case for untrusted plan handling."""

    case_id: str
    payload: object
    expected_code: str
    settings_overrides: dict[str, int] | None = None


def _bad_top_level_key(rng: random.Random) -> object:
    """Generate a deterministic invalid top-level mapping key."""

    return rng.choice([1, 2.5, ("tuple",)])


def _build_seeded_cases() -> list[_GeneratedCase]:
    """Build a bounded set of deterministic rejection cases from fixed seed."""

    rng = random.Random(GENERATION_SEED)
    cases: list[_GeneratedCase] = []
    valid_list_plan = status_plan().model_dump(mode="json")
    valid_aggregate_plan = {
        "resource": "orders",
        "intent": "aggregate",
        "filters": [],
        "group_by": [{"field": "status"}],
        "metrics": [{"metric": "order_count"}],
        "order_by": [],
        "limit": 10,
    }
    valid_query_bytes = json.dumps(valid_list_plan, separators=(",", ":")).encode(
        "utf-8"
    )

    malformed = [
        "{",
        '{"resource": "orders", "intent": "list"',
        '"not-a-string"',
        json.dumps(valid_list_plan)[:-1],
    ]
    for index, raw_plan in enumerate(malformed):
        cases.append(
            _GeneratedCase(
                case_id=f"seed{GENERATION_SEED}-malformed-json-{index:02d}",
                payload=raw_plan,
                expected_code="asklens.parse.invalid",
            )
        )

    cases.extend(
        [
            _GeneratedCase(
                case_id=f"seed{GENERATION_SEED}-invalid-bytes-utf8",
                payload=b"\xff\xfe\xfd",
                expected_code="asklens.parse.invalid",
            ),
            _GeneratedCase(
                case_id=f"seed{GENERATION_SEED}-invalid-json-key",
                payload={
                    "resource": "orders",
                    "intent": "list",
                    _bad_top_level_key(rng): "x",
                },
                expected_code="asklens.parse.invalid",
            ),
        ]
    )

    extra_key = f"__hidden_{rng.randint(10_000, 99_999)}"
    extra_key_payload = copy.deepcopy(valid_list_plan)
    extra_key_payload[extra_key] = "raw_sql"
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-strict-shape-extra-key",
            payload=extra_key_payload,
            expected_code="asklens.parse.invalid",
        )
    )

    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-strict-shape-nested",
            payload={
                "resource": "orders",
                "intent": "list",
                "select": {"field": "status"},
                "limit": 10,
            },
            expected_code="asklens.parse.invalid",
        )
    )

    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-strict-shape-order-by-ambiguous",
            payload={
                "resource": "orders",
                "intent": "list",
                "select": ["status"],
                "order_by": [
                    {
                        "field": "status",
                        "metric": "order_count",
                        "direction": "asc",
                    }
                ],
                "limit": 10,
            },
            expected_code="asklens.parse.invalid",
        )
    )

    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-opaque-resource",
            payload={
                "resource": f"orders_{rng.randint(10_000, 99_999)}",
                "intent": "list",
                "select": ["status"],
                "limit": 10,
            },
            expected_code="asklens.member.unavailable",
        )
    )

    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-opaque-field",
            payload={
                "resource": "orders",
                "intent": "list",
                "select": ["status", f"missing_{rng.randint(10_000, 99_999)}"],
                "limit": 10,
            },
            expected_code="asklens.member.unavailable",
        )
    )

    opaque_metric = copy.deepcopy(valid_aggregate_plan)
    opaque_metric["metrics"] = [{"metric": f"revenue_{rng.randint(10_000, 99_999)}"}]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-opaque-metric",
            payload=opaque_metric,
            expected_code="asklens.member.unavailable",
        )
    )

    mismatch_status = copy.deepcopy(valid_list_plan)
    mismatch_status["filters"] = [
        {"field": "status", "op": "eq", "value": rng.randint(10_000, 99_999)}
    ]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-type-mismatch-status-int",
            payload=mismatch_status,
            expected_code="asklens.plan.invalid",
        )
    )

    mismatch_integer = copy.deepcopy(valid_list_plan)
    mismatch_integer["filters"] = [
        {
            "field": "id",
            "op": "eq",
            "value": "not-an-integer",
        }
    ]
    mismatch_integer["order_by"] = []
    mismatch_integer["select"] = ["status"]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-type-mismatch-id-string",
            payload=mismatch_integer,
            expected_code="asklens.plan.invalid",
        )
    )

    over_filters = copy.deepcopy(valid_list_plan)
    over_filters["filters"] = [
        {"field": "status", "op": "eq", "value": "paid"},
        {"field": "status", "op": "neq", "value": "pending"},
    ]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-budget-over-filters",
            payload=over_filters,
            expected_code="asklens.budget.exceeded",
            settings_overrides={"MAX_FILTERS": 1},
        )
    )

    over_selected_fields = copy.deepcopy(valid_list_plan)
    over_selected_fields["select"] = ["id", "status"]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-budget-over-selected-fields",
            payload=over_selected_fields,
            expected_code="asklens.budget.exceeded",
            settings_overrides={"MAX_SELECTED_FIELDS": 1},
        )
    )

    over_order_by = copy.deepcopy(valid_list_plan)
    over_order_by["order_by"] = [
        {"field": "id", "direction": "asc"},
        {"field": "status", "direction": "desc"},
    ]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-budget-over-order-by",
            payload=over_order_by,
            expected_code="asklens.budget.exceeded",
            settings_overrides={"MAX_ORDER_BY": 1},
        )
    )

    over_in_values = copy.deepcopy(valid_list_plan)
    over_in_values["filters"] = [
        {
            "field": "status",
            "op": "in",
            "value": ["paid", "pending", "failed"],
        }
    ]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-budget-over-in-values",
            payload=over_in_values,
            expected_code="asklens.budget.exceeded",
            settings_overrides={"MAX_IN_VALUES": 1},
        )
    )

    over_results = {
        "resource": "orders",
        "intent": "list",
        "select": ["status"],
        "limit": 2,
    }
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-budget-over-result-rows",
            payload=over_results,
            expected_code="asklens.budget.exceeded",
            settings_overrides={"MAX_ROWS": 1, "DEFAULT_LIMIT": 1},
        )
    )

    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-budget-over-plan-bytes",
            payload=valid_query_bytes,
            expected_code="asklens.budget.exceeded",
            settings_overrides={"MAX_PLAN_BYTES": len(valid_query_bytes) - 1},
        )
    )

    return cases


GENERATED_REJECTION_CASES = _build_seeded_cases()


def configure_custom_audit(settings, events: list[dict]) -> None:
    """Attach metadata-only in-memory audit sink used by generated-rejection tests."""

    def _sink(event: dict) -> None:
        events.append(event)

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "custom",
        "AUDIT_SINK": _sink,
        "AUDIT_INCLUDE_CONTENT": False,
    }


@pytest.mark.parametrize(
    "case", GENERATED_REJECTION_CASES, ids=lambda case: case.case_id
)
@pytest.mark.django_db
def test_generated_rejection_cases_have_safe_error_envelope_and_no_application_sql(
    settings,
    case: _GeneratedCase,
    django_assert_num_queries,
) -> None:
    """Generated invalid payloads must fail safely and before application-data SQL."""

    events: list[dict] = []
    configure_custom_audit(settings, events)
    request = request_with("shop.view_orders")
    if case.settings_overrides is not None:
        settings.DJANGO_ASKLENS.update(case.settings_overrides)

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(case.payload, request=request, registry=build_registry())

    error = caught.value
    public_payload = public_error_payload(error)

    assert public_payload["code"] == case.expected_code
    assert public_payload["message"] == EXPECTED_PUBLIC_MESSAGES[case.expected_code]
    assert str(error) == public_payload["message"]
    assert case.case_id not in str(error)
    assert case.case_id not in "".join(traceback.format_exception(error))

    assert len(events) == 1
    [audit_event] = events
    assert audit_event["status"] == "failed"
    assert audit_event["error_code"] == case.expected_code
    assert audit_event["error_message"] == public_payload["message"]
    assert "question" not in audit_event
    assert "plan" not in audit_event
    assert "raw_sql" not in str(audit_event)


@pytest.mark.parametrize(
    "raw_plan",
    [123, 12.34, ["not", "a", "plan"], {"a", "b"}],
    ids=["int", "float", "list", "set"],
)
@pytest.mark.django_db
def test_unsupported_input_containers_reject_with_parse_error(
    settings,
    raw_plan: object,
    django_assert_num_queries,
) -> None:
    """Only str/bytes/mapping/QueryPlan are accepted plan input container types."""

    events: list[dict] = []
    configure_custom_audit(settings, events)
    request = request_with("shop.view_orders")
    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(raw_plan, request=request, registry=build_registry())

    public_error = public_error_payload(caught.value)
    assert public_error == {
        "code": "asklens.parse.invalid",
        "message": "The query plan could not be parsed.",
    }
    assert len(events) == 1


@pytest.mark.parametrize(
    "input_plan",
    [
        status_plan(),
        status_plan().model_dump(mode="json"),
        json.dumps(status_plan().model_dump(mode="json")),
        json.dumps(status_plan().model_dump(mode="json")).encode("utf-8"),
    ],
    ids=["query-plan", "mapping", "json-string", "json-bytes"],
)
@pytest.mark.django_db
def test_supported_plan_container_types_execute_and_validate(
    settings,
    input_plan,
    django_assert_num_queries,
) -> None:
    """Supported plan container types are accepted through execute_plan()."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}
    request = request_with("shop.view_orders")

    with django_assert_num_queries(1):
        result = execute_plan(input_plan, request=request, registry=build_registry())

    assert result.row_count >= 0
    assert len(result.columns) == 1
    assert result.columns[0].key == "status"


@pytest.mark.parametrize(
    "raw_plan",
    [
        b"{\x80\x81",
        "{",
        '"not-an-object"',
        {"resource": 1},
    ],
    ids=["invalid-utf8", "malformed-json", "non-object-json", "bad-resource-type"],
)
def test_parse_query_plan_errors_are_stable_and_safe(raw_plan: object) -> None:
    """Pure parsing rejects malformed payloads with stable public envelopes."""

    with pytest.raises(PlanParseError) as caught:
        parse_query_plan(raw_plan)

    public_error = public_error_payload(normalize_public_error(caught.value))
    assert public_error == {
        "code": "asklens.parse.invalid",
        "message": "The query plan could not be parsed.",
    }
    assert "raw_sql" not in public_error["message"]


def test_parse_query_plan_accepts_valid_query_plan_input() -> None:
    """A valid mapping parses into QueryPlan without changing public shape."""

    parsed = parse_query_plan(status_plan().model_dump(mode="json"))
    assert isinstance(parsed, QueryPlan)
