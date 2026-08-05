"""Deterministic stdlib-generated untrusted-plan boundary tests.

These tests provide synthetic safety evidence only and intentionally avoid
changing production runtime behavior.
"""

import copy
import json
import os
import random
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

FORBIDDEN_PUBLIC_MARKERS = (
    "traceback",
    "tenant",
    "permission",
    "secret",
    "credential",
    "customer__email",
    "order__",
    "order.objects",
)
DISTINCTIVE_NUMERIC_PRIVATE_TOKEN_MIN = 9_000_000_000


def _generation_seed() -> int:
    """Read deterministic seed from test environment.

    Replay expects an integer string for deterministic cases.
    """

    raw_seed = os.getenv("ASKLENS_HARDENING_GENERATION_SEED", "20260805")
    try:
        return int(raw_seed)
    except ValueError as exc:
        raise ValueError(
            "ASKLENS_HARDENING_GENERATION_SEED must be an integer "
            "for deterministic replay."
        ) from exc


GENERATION_SEED = _generation_seed()

EXPECTED_PUBLIC_MESSAGES = {
    "asklens.parse.invalid": "The query plan could not be parsed.",
    "asklens.member.unavailable": "A requested query member is unavailable.",
    "asklens.plan.invalid": "The query plan is invalid.",
    "asklens.budget.exceeded": "The query plan exceeds an execution limit.",
}


@dataclass(frozen=True)
class _GeneratedCase:
    """One bounded synthetic failure case for untrusted-plan handling."""

    case_id: str
    payload: object
    expected_code: str
    settings_overrides: dict[str, int] | None = None
    private_tokens: tuple[str, ...] = ()


def _value_text(value: object) -> str:
    """Return a compact stable string for private token checks."""

    if isinstance(value, str):
        return value
    if isinstance(value, (bool, int, float)):
        return str(value)
    try:
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _private_tokens(*values: object) -> tuple[str, ...]:
    """Collect deterministic private tokens for safe-surface assertions."""

    return tuple(dict.fromkeys(_value_text(value) for value in values))


def _distinctive_numeric_private_token(rng: random.Random) -> int:
    """Return a numeric leak sentinel unlikely to match safe operational metadata.

    This large synthetic range prevents substring-test false positives; it is not a
    production input or audit policy.
    """

    return DISTINCTIVE_NUMERIC_PRIVATE_TOKEN_MIN + rng.randint(10_000, 99_999)


def _generate_scalar_json_value(rng: random.Random) -> object:
    """Generate bounded primitive JSON values."""

    return rng.choice(
        [
            None,
            True,
            False,
            # Preserve this generator's original bounded RNG draw while ensuring a
            # numeric payload sentinel cannot resemble timestamp/duration metadata.
            DISTINCTIVE_NUMERIC_PRIVATE_TOKEN_MIN + rng.randint(0, 50),
            f"seed-{GENERATION_SEED}-{rng.randint(10_000, 99_999)}",
        ]
    )


def _generate_json_value(rng: random.Random, max_depth: int) -> object:
    """Generate a bounded recursive JSON value for deterministic variation."""

    if max_depth <= 0:
        return _generate_scalar_json_value(rng)

    branch = rng.choice(["scalar", "list", "dict"])
    if branch == "scalar" or max_depth <= 1:
        return _generate_scalar_json_value(rng)

    if branch == "list":
        return [
            _generate_json_value(rng, max_depth=max_depth - 1),
            _generate_json_value(rng, max_depth=max_depth - 1),
        ]

    return {
        f"sentinel_{rng.randint(10_000, 99_999)}": _generate_json_value(
            rng, max_depth=max_depth - 1
        ),
        f"marker_{rng.randint(10_000, 99_999)}": _generate_json_value(
            rng, max_depth=max_depth - 1
        ),
    }


def _bounded_json_values(rng: random.Random, count: int = 4) -> list[object]:
    """Return a bounded set of synthetic JSON values for case generation."""

    return [_generate_json_value(rng, max_depth=2) for _ in range(count)]


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
                    (1, 2.5): "x",
                },
                expected_code="asklens.parse.invalid",
            ),
        ]
    )

    for index, sentinel in enumerate(_bounded_json_values(rng, count=4), start=1):
        key = f"__hidden_{rng.randint(10_000, 99_999)}_{index}"
        payload = copy.deepcopy(valid_list_plan)
        payload[key] = sentinel
        cases.append(
            _GeneratedCase(
                case_id=f"seed{GENERATION_SEED}-strict-shape-extra-key-{index:02d}",
                payload=payload,
                expected_code="asklens.parse.invalid",
                private_tokens=(_value_text(key), *_private_tokens(sentinel)),
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
            private_tokens=("field",),
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
            private_tokens=("order_count",),
        )
    )

    opaque_resource = f"orders_{rng.randint(10_000, 99_999)}"
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-opaque-resource",
            payload={
                "resource": opaque_resource,
                "intent": "list",
                "select": ["status"],
                "limit": 10,
            },
            expected_code="asklens.member.unavailable",
            private_tokens=(_value_text(opaque_resource),),
        )
    )

    opaque_field = f"missing_{rng.randint(10_000, 99_999)}"
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-opaque-field",
            payload={
                "resource": "orders",
                "intent": "list",
                "select": ["status", opaque_field],
                "limit": 10,
            },
            expected_code="asklens.member.unavailable",
            private_tokens=(opaque_field,),
        )
    )

    opaque_metric = copy.deepcopy(valid_aggregate_plan)
    hidden_metric = f"revenue_{rng.randint(10_000, 99_999)}"
    opaque_metric["metrics"] = [{"metric": hidden_metric}]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-opaque-metric",
            payload=opaque_metric,
            expected_code="asklens.member.unavailable",
            private_tokens=(hidden_metric,),
        )
    )

    mismatch_status_token = _distinctive_numeric_private_token(rng)
    mismatch_status = copy.deepcopy(valid_list_plan)
    mismatch_status["filters"] = [
        {"field": "status", "op": "eq", "value": mismatch_status_token}
    ]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-type-mismatch-status-int",
            payload=mismatch_status,
            expected_code="asklens.plan.invalid",
            private_tokens=(str(mismatch_status_token),),
        )
    )

    mismatch_integer = copy.deepcopy(valid_list_plan)
    mismatch_integer_value = f"not-an-integer-{rng.randint(10_000, 99_999)}"
    mismatch_integer["filters"] = [
        {
            "field": "id",
            "op": "eq",
            "value": mismatch_integer_value,
        }
    ]
    mismatch_integer["order_by"] = []
    mismatch_integer["select"] = ["status"]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-type-mismatch-id-string",
            payload=mismatch_integer,
            expected_code="asklens.plan.invalid",
            private_tokens=(mismatch_integer_value,),
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

    over_group_by = copy.deepcopy(valid_aggregate_plan)
    over_group_by["group_by"] = [
        {"field": "status"},
        {"field": "id"},
        {"field": "status"},
    ]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-budget-over-group-by",
            payload=over_group_by,
            expected_code="asklens.budget.exceeded",
            settings_overrides={"MAX_GROUP_BY": 1},
        )
    )

    over_metrics = copy.deepcopy(valid_aggregate_plan)
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-budget-over-metrics",
            payload=over_metrics,
            expected_code="asklens.budget.exceeded",
            settings_overrides={"MAX_METRICS": 0},
        )
    )

    over_filter_values = copy.deepcopy(valid_list_plan)
    over_filter_value = _distinctive_numeric_private_token(rng)
    over_filter_values["filters"] = [
        {"field": "status", "op": "eq", "value": "paid"},
        {"field": "status", "op": "neq", "value": "pending"},
        {
            "field": "id",
            "op": "eq",
            "value": over_filter_value,
        },
    ]
    cases.append(
        _GeneratedCase(
            case_id=f"seed{GENERATION_SEED}-budget-over-filter-values",
            payload=over_filter_values,
            expected_code="asklens.budget.exceeded",
            settings_overrides={"MAX_FILTER_VALUES": 2},
            private_tokens=(str(over_filter_value),),
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


def test_generated_numeric_private_tokens_use_distinctive_synthetic_range() -> None:
    """Numeric leak sentinels cannot collide with ordinary operational metadata."""

    numeric_tokens = [
        (case.case_id, token)
        for case in GENERATED_REJECTION_CASES
        for token in case.private_tokens
        if token.isdecimal()
    ]
    assert numeric_tokens
    invalid_numeric_tokens = [
        (case_id, token)
        for case_id, token in numeric_tokens
        if len(token) < 10 or int(token) < DISTINCTIVE_NUMERIC_PRIVATE_TOKEN_MIN
    ]
    assert invalid_numeric_tokens == []


def configure_custom_audit(settings, events: list[dict]) -> None:
    """Attach metadata-only in-memory audit sink used by generated-rejection tests."""

    def _sink(event: dict) -> None:
        events.append(event)

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "custom",
        "AUDIT_SINK": _sink,
        "AUDIT_INCLUDE_CONTENT": False,
    }


def _assert_no_token_leaks(
    *,
    case: _GeneratedCase,
    public_payload_text: str,
    error_text: str,
    event_text: str,
) -> None:
    """Assert deterministic private tokens never leak into public-facing output."""

    combined_text = public_payload_text + error_text + event_text
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in combined_text.lower()

    for token in case.private_tokens:
        if token:
            assert token not in public_payload_text
            assert token not in error_text
            assert token not in event_text


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
    error_text = str(error)
    public_payload_text = json.dumps(
        public_payload, sort_keys=True, separators=(",", ":"), default=str
    )
    assert public_payload["code"] == case.expected_code
    assert public_payload["message"] == EXPECTED_PUBLIC_MESSAGES[case.expected_code]
    assert error_text == public_payload["message"]

    assert len(events) == 1
    [audit_event] = events
    audit_event_text = json.dumps(
        audit_event, sort_keys=True, separators=(",", ":"), default=str
    )
    assert audit_event["status"] == "failed"
    assert audit_event["error_code"] == case.expected_code
    assert audit_event["error_message"] == public_payload["message"]
    assert "question" not in audit_event
    assert "plan" not in audit_event
    assert "raw_sql" not in str(audit_event)

    _assert_no_token_leaks(
        case=case,
        public_payload_text=public_payload_text,
        error_text=error_text,
        event_text=audit_event_text,
    )


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
    public_text = json.dumps(public_error, sort_keys=True, separators=(",", ":"))
    assert public_error == {
        "code": "asklens.parse.invalid",
        "message": "The query plan could not be parsed.",
    }
    assert "traceback" not in public_text.lower()
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
    public_text = json.dumps(public_error, sort_keys=True, separators=(",", ":"))
    assert public_error == {
        "code": "asklens.parse.invalid",
        "message": "The query plan could not be parsed.",
    }
    assert "traceback" not in public_text.lower()
    assert "raw_sql" not in public_text


def test_parse_query_plan_accepts_valid_query_plan_input() -> None:
    """A valid mapping parses into QueryPlan without changing public shape."""

    parsed = parse_query_plan(status_plan().model_dump(mode="json"))
    assert isinstance(parsed, QueryPlan)
