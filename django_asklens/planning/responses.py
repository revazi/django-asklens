"""Unified provider response planning for AskLens query/help requests."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError, model_validator

from django_asklens.catalog.capabilities import CapabilitiesSnapshot
from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.exceptions import PlanValidationError
from django_asklens.llms.base import LLMMessage, LLMProvider
from django_asklens.llms.factory import get_llm_provider
from django_asklens.planning.help import (
    QueryHelp,
    limit_query_help_suggestions,
    requested_suggestion_count,
    validate_query_help,
)
from django_asklens.planning.prompts import stable_json_dumps
from django_asklens.planning.schemas import (
    PLAN_MODEL_CONFIG,
    PlanBaseModel,
    QueryPlan,
    format_pydantic_error,
    parse_plan_payload,
)
from django_asklens.planning.validation import PlanLimits, parse_and_validate_query_plan

ResponseType = Literal["query", "capabilities"]

UNIFIED_RESPONSE_SYSTEM_PROMPT = """You are Django AskLens' unified planner.
Return only JSON matching the provided AskLensProviderResponse schema.
Use response_type="capabilities" when the user asks what AskLens can query,
which resources/entities/fields/metrics are available, example questions,
suggested queries, or help using AskLens.
Use response_type="query" when the user asks for actual records, rows, counts,
totals, trends, filtered data, or aggregate results.
Use only resources, fields, metrics, date fields, and scope guidance present in
the visible capabilities metadata. Never invent resources, fields, metrics,
model names, table names, permissions, SQL, code, or explanations.

For response_type="query", return query_plan and omit query_help. QueryPlan
must be read-only and use exact resource, field, metric, and date field names
from capabilities. Use aggregate plans for counts, sums, averages, totals,
trends, and "by ..." grouping questions. Aggregate plans must put dimensions in
group_by only and must not include select. Use list plans only when the user
asks to list records or fields. List plans use select and must not include
metrics or group_by. Result keys are exact select field names, group_by field
names, and metric names. For date_trunc groupings, visualization axes and
order_by fields must still reference the original group_by field name; never
invent bucket aliases such as "start_date_month".

For response_type="capabilities", return query_help and omit query_plan. Query
help suggestions must include natural-language question text plus exact
resource_name and referenced field, metric, and date_field names. Do not include
plan JSON in suggestions; AskLens builds executable plans locally. Prefer fresh,
diverse, useful suggestions across visible operational resources unless the user
asks about a specific resource. Do not include database rows, sample values,
secrets, credentials, mutation requests, SQL, or unavailable fields/resources.
If a resource scope has level="single", suggestions must be phrased within that
single visible scope; do not suggest comparing, grouping, filtering, or trending
across a scope dimension unless the resource scope allows multiple/all scopes
and the scope-dimension field is visible.
""".strip()


class AskLensProviderResponse(PlanBaseModel):
    """Strict unified response returned by a provider."""

    model_config = PLAN_MODEL_CONFIG

    response_type: ResponseType
    query_plan: dict[str, Any] | None = None
    query_help: QueryHelp | None = None

    @model_validator(mode="after")
    def validate_response_branch(self) -> "AskLensProviderResponse":
        """Require exactly the branch matching response_type."""

        if self.response_type == "query":
            if self.query_plan is None:
                msg = "response_type='query' requires query_plan."
                raise ValueError(msg)
            if self.query_help is not None:
                msg = "response_type='query' must not include query_help."
                raise ValueError(msg)
            return self

        if self.query_help is None:
            msg = "response_type='capabilities' requires query_help."
            raise ValueError(msg)
        if self.query_plan is not None:
            msg = "response_type='capabilities' must not include query_plan."
            raise ValueError(msg)
        return self


@dataclass(frozen=True, slots=True)
class AskLensProviderResult:
    """Validated unified provider response."""

    question: str
    response_type: ResponseType
    query_plan: QueryPlan | None = None
    query_help: QueryHelp | None = None


def plan_asklens_response(
    question: str,
    *,
    capabilities: CapabilitiesSnapshot,
    provider: LLMProvider | None = None,
    registry: CatalogRegistry = default_registry,
    limits: PlanLimits | None = None,
    permissions: Iterable[str] | None = None,
) -> AskLensProviderResult:
    """Ask a provider for either a query plan or capability help in one call."""

    permission_set = tuple(permissions or ())
    selected_provider = provider or get_llm_provider()
    payload = selected_provider.complete_json(
        messages=build_unified_response_messages(
            question=question,
            capabilities=capabilities,
            suggestion_count=requested_suggestion_count(question),
        ),
        schema=get_asklens_provider_response_json_schema(),
    )
    response = parse_asklens_provider_response(payload)

    if response.response_type == "query":
        assert response.query_plan is not None  # Narrowed by branch validator.
        validated_plan = parse_and_validate_query_plan(
            response.query_plan,
            registry=registry,
            limits=limits,
            permissions=permission_set,
        )
        return AskLensProviderResult(
            question=question,
            response_type="query",
            query_plan=validated_plan,
        )

    assert response.query_help is not None  # Narrowed by branch validator.
    query_help = validate_query_help(
        response.query_help,
        capabilities=capabilities,
        registry=registry,
        permissions=permission_set,
        require_plans=True,
    )
    query_help = limit_query_help_suggestions(
        query_help,
        suggestion_count=requested_suggestion_count(question),
    )
    return AskLensProviderResult(
        question=question,
        response_type="capabilities",
        query_help=query_help,
    )


def build_unified_response_messages(
    *,
    question: str,
    capabilities: CapabilitiesSnapshot,
    suggestion_count: int,
) -> tuple[LLMMessage, ...]:
    """Build messages for a single provider query/help decision."""

    return (
        {"role": "system", "content": UNIFIED_RESPONSE_SYSTEM_PROMPT},
        {"role": "user", "content": question},
        {
            "role": "user",
            "content": (
                "If response_type is capabilities, return up to "
                f"{suggestion_count} usable example questions. Do not exceed "
                "this count."
            ),
        },
        {
            "role": "user",
            "content": "Visible capabilities metadata:\n"
            + stable_json_dumps(capabilities),
        },
    )


def parse_asklens_provider_response(
    raw_response: str | bytes | Mapping[str, Any],
) -> AskLensProviderResponse:
    """Parse untrusted provider output into a strict unified response."""

    payload = normalize_provider_response_payload(parse_plan_payload(raw_response))
    try:
        return AskLensProviderResponse.model_validate(payload)
    except ValidationError as exc:
        msg = format_pydantic_error(exc).replace("QueryPlan", "AskLensProviderResponse")
        raise PlanValidationError(msg) from exc


def normalize_provider_response_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a normalized copy of a compact provider response payload.

    The compact live-provider schema cannot express conditional rules such as
    "aggregate plans must not include select" without triggering provider schema
    complexity limits. Some providers include group_by dimensions in select for
    aggregate plans. That is redundant and not executable output shape, so we
    drop only the safe duplicate case before normal QueryPlan validation. Any
    aggregate select that is not already present in group_by is left intact and
    rejected by the core validator.
    """

    normalized = dict(payload)
    query_plan = normalized.get("query_plan")
    if isinstance(query_plan, Mapping):
        normalized["query_plan"] = normalize_compact_query_plan(query_plan)
    return normalized


def normalize_compact_query_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return a normalized copy of a compact provider query plan."""

    normalized = dict(plan)
    if normalized.get("intent") != "aggregate" or "select" not in normalized:
        return normalized

    select = normalized.get("select")
    group_by = normalized.get("group_by")
    if is_group_by_duplicate_select(select=select, group_by=group_by):
        normalized.pop("select", None)
    return normalized


def is_group_by_duplicate_select(*, select: Any, group_by: Any) -> bool:
    """Return whether aggregate select only repeats group_by result keys."""

    if not isinstance(select, list):
        return False
    if not select:
        return True
    if not isinstance(group_by, list):
        return False

    group_fields = {
        item.get("field")
        for item in group_by
        if isinstance(item, Mapping) and isinstance(item.get("field"), str)
    }
    return all(isinstance(item, str) and item in group_fields for item in select)


def get_asklens_provider_response_json_schema() -> dict[str, Any]:
    """Return a compact provider-facing unified response JSON schema.

    The runtime parser still validates provider output with Pydantic and
    AskLens' normal QueryPlan/QueryHelp validation. This schema is intentionally
    flatter than the internal Pydantic schema because some OpenAI-compatible
    providers reject deeply nested schemas with many states.
    """

    return {
        "title": "AskLensProviderResponse",
        "description": "Unified AskLens provider response.",
        "type": "object",
        "additionalProperties": False,
        "required": ["response_type"],
        "properties": {
            "response_type": {
                "type": "string",
                "enum": ["query", "capabilities"],
            },
            "query_plan": compact_query_plan_schema(),
            "query_help": compact_query_help_schema(),
        },
    }


def compact_query_plan_schema() -> dict[str, Any]:
    """Return a compact provider-facing QueryPlan-like schema."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["resource", "intent"],
        "properties": {
            "resource": {"type": "string"},
            "intent": {"type": "string", "enum": ["list", "aggregate"]},
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["field", "op"],
                    "properties": {
                        "field": {"type": "string"},
                        "op": {
                            "type": "string",
                            "enum": [
                                "eq",
                                "neq",
                                "contains",
                                "icontains",
                                "gt",
                                "gte",
                                "lt",
                                "lte",
                                "in",
                                "isnull",
                                "date_range",
                                "last_n_days",
                                "last_n_months",
                            ],
                        },
                        "value": compact_json_value_schema(),
                    },
                },
            },
            "group_by": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["field"],
                    "properties": {
                        "field": {"type": "string"},
                        "date_trunc": {
                            "type": "string",
                            "enum": ["day", "week", "month", "quarter", "year"],
                        },
                    },
                },
            },
            "metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "op", "field"],
                    "properties": {
                        "name": {"type": "string"},
                        "op": {
                            "type": "string",
                            "enum": ["count", "sum", "avg", "min", "max"],
                        },
                        "field": {"type": "string"},
                    },
                },
            },
            "select": {"type": "array", "items": {"type": "string"}},
            "order_by": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field": {"type": "string"},
                        "metric": {"type": "string"},
                        "direction": {"type": "string", "enum": ["asc", "desc"]},
                    },
                },
            },
            "limit": {"type": "integer"},
            "visualization": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["table", "metric", "bar", "line", "pie"],
                    },
                    "x": {"type": "string"},
                    "y": {"type": "string"},
                },
            },
        },
    }


def compact_json_value_schema() -> dict[str, Any]:
    """Return a compact schema for filter values."""

    return {
        "type": ["string", "integer", "number", "boolean", "array", "null"],
        "items": {"type": ["string", "integer", "number", "boolean", "null"]},
    }


def compact_query_help_schema() -> dict[str, Any]:
    """Return a compact provider-facing QueryHelp-like schema."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["answer"],
        "properties": {
            "answer": {"type": "string"},
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["question", "resource_name"],
                    "properties": {
                        "question": {"type": "string"},
                        "resource_name": {"type": "string"},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "metrics": {"type": "array", "items": {"type": "string"}},
                        "date_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "why": {"type": "string"},
                    },
                },
            },
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    }
