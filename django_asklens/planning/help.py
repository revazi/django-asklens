"""Provider-backed help for generating safe AskLens query questions."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import Field, ValidationError, field_validator

from django_asklens.catalog.capabilities import (
    CapabilitiesSnapshot,
    CapabilityResource,
    humanize_scope_kind,
    is_scope_dimension_field,
    is_single_scope_resource,
    pluralize_scope_kind,
)
from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.exceptions import PlanValidationError
from django_asklens.llms.base import LLMMessage, LLMProvider
from django_asklens.llms.factory import get_llm_provider
from django_asklens.planning.prompts import stable_json_dumps
from django_asklens.planning.schemas import (
    PLAN_MODEL_CONFIG,
    PlanBaseModel,
    QueryPlan,
    format_pydantic_error,
    parse_plan_payload,
    validate_non_empty_string,
)
from django_asklens.planning.validation import parse_and_validate_query_plan

DEFAULT_HELP_SUGGESTIONS = 5
MAX_HELP_SUGGESTIONS = 10
MAX_REFERENCE_COUNT = 8
BLOCKED_SUGGESTION_ACTIONS = {
    "create",
    "delete",
    "drop",
    "insert",
    "mutate",
    "truncate",
    "update",
    "upsert",
}

QUERY_HELP_SYSTEM_PROMPT = """You help users write safe Django AskLens questions.
Return only JSON matching the provided QueryHelp schema.
Use only resources, fields, metrics, date fields, and scope guidance present
in the visible capabilities metadata.
Suggest natural-language questions that AskLens can plan as read-only list or
aggregate queries. Suggestions must be copy-pasteable user questions likely to
produce valid AskLens plans. For broad help questions like "what can I query?",
provide fresh, diverse suggestions across useful visible resources; prefer
analytical aggregate or trend questions over simple lookup/list questions unless
the user asks about a specific lookup resource.
For each suggestion, include the exact resource_name and referenced field,
metric, and date_field names from the metadata. AskLens will build executable
plans locally from those references; do not include plan JSON. Do not simply
copy generated examples from the metadata when better provider-generated
suggestions are possible.
If a resource scope has level="single", suggestions must be phrased within
that single visible scope. Do not suggest comparing, grouping, filtering, or
trending across any scope dimension unless the resource scope allows multiple
or all scopes and the scope-dimension field is visible.
Do not suggest internal result-key aliases such as "start_date_month"; say
"by month using start date" in the natural-language question instead. For
visualization, use table with no axes when a chart is not clearly needed; use
metric with y set to the metric name for single-number aggregate answers.
If the user asks for a number of examples, return up to the requested count,
never more than the requested count from the additional instructions.
Do not include SQL, code, database rows, sample values, secrets, credentials,
mutation requests, or unavailable fields/resources.
""".strip()


class QueryHelpSuggestion(PlanBaseModel):
    """One suggested AskLens question with catalog references."""

    model_config = PLAN_MODEL_CONFIG

    question: str
    resource_name: str
    fields: tuple[str, ...] = Field(
        default_factory=tuple, max_length=MAX_REFERENCE_COUNT
    )
    metrics: tuple[str, ...] = Field(
        default_factory=tuple, max_length=MAX_REFERENCE_COUNT
    )
    date_fields: tuple[str, ...] = Field(
        default_factory=tuple,
        max_length=MAX_REFERENCE_COUNT,
    )
    plan: dict[str, Any] | None = Field(
        default=None,
        description="A QueryPlan JSON object that answers this suggested question.",
    )
    why: str = ""

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        """Validate suggested question text."""

        return validate_non_empty_string(value, "suggested question")

    @field_validator("resource_name")
    @classmethod
    def validate_resource_name(cls, value: str) -> str:
        """Validate suggested resource name."""

        return validate_non_empty_string(value, "resource name")

    @field_validator("fields", "metrics", "date_fields")
    @classmethod
    def validate_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Validate catalog reference names."""

        return tuple(
            validate_non_empty_string(item, "catalog reference") for item in value
        )


class QueryHelp(PlanBaseModel):
    """Strict provider output for help generating AskLens questions."""

    model_config = PLAN_MODEL_CONFIG

    answer: str
    suggestions: tuple[QueryHelpSuggestion, ...] = Field(
        default_factory=tuple,
        max_length=MAX_HELP_SUGGESTIONS,
    )
    notes: tuple[str, ...] = Field(default_factory=tuple, max_length=5)

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        """Validate the short help answer."""

        return validate_non_empty_string(value, "help answer")

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Validate note strings."""

        return tuple(validate_non_empty_string(item, "help note") for item in value)


def build_query_help(
    question: str,
    *,
    capabilities: CapabilitiesSnapshot,
    provider: LLMProvider | None = None,
    registry: CatalogRegistry = default_registry,
    permissions: Sequence[str] | None = None,
) -> QueryHelp:
    """Ask a provider for safe query-writing help and validate the response."""

    suggestion_count = requested_suggestion_count(question)
    selected_provider = provider or get_llm_provider()
    payload = selected_provider.complete_json(
        messages=build_query_help_messages(
            question=question,
            capabilities=capabilities,
            suggestion_count=suggestion_count,
        ),
        schema=get_query_help_json_schema(),
    )
    permission_set = tuple(permissions or ())
    help_result = validate_query_help(
        parse_query_help(payload),
        capabilities=capabilities,
        registry=registry,
        permissions=permission_set,
        require_plans=True,
    )
    return limit_query_help_suggestions(
        help_result,
        suggestion_count=suggestion_count,
    )


def requested_suggestion_count(question: str) -> int:
    """Return desired suggestion count parsed from a help question."""

    count_patterns = (
        r"\b(?:give|show|list|suggest|return)\s+me\s+(?P<count>\d{1,2})\b",
        r"\b(?:give|show|list|suggest|return)\s+(?P<count>\d{1,2})\b",
        r"\b(?P<count>\d{1,2})\s+(?:example|examples|question|questions|suggestion|suggestions)\b",
    )
    for pattern in count_patterns:
        match = re.search(pattern, question.lower())
        if match is not None:
            return clamp_suggestion_count(int(match.group("count")))
    return DEFAULT_HELP_SUGGESTIONS


def clamp_suggestion_count(count: int) -> int:
    """Clamp requested help suggestion counts to supported bounds."""

    return max(1, min(count, MAX_HELP_SUGGESTIONS))


def limit_query_help_suggestions(
    help_result: QueryHelp,
    *,
    suggestion_count: int,
) -> QueryHelp:
    """Limit provider suggestions to the requested count."""

    if len(help_result.suggestions) <= suggestion_count:
        return help_result
    return QueryHelp(
        answer=help_result.answer,
        suggestions=help_result.suggestions[:suggestion_count],
        notes=help_result.notes,
    )


def build_query_help_messages(
    *,
    question: str,
    capabilities: CapabilitiesSnapshot,
    suggestion_count: int | None = None,
) -> tuple[LLMMessage, ...]:
    """Build provider messages for strict query-help generation."""

    desired_count = suggestion_count or DEFAULT_HELP_SUGGESTIONS
    return (
        {"role": "system", "content": QUERY_HELP_SYSTEM_PROMPT},
        {"role": "user", "content": question},
        {
            "role": "user",
            "content": (
                "Suggestion instructions:\n"
                f"Return up to {desired_count} usable example questions. "
                "Do not exceed this count."
            ),
        },
        {
            "role": "user",
            "content": "Visible capabilities metadata:\n"
            + stable_json_dumps(capabilities),
        },
    )


def parse_query_help(raw_help: str | bytes | Mapping[str, Any]) -> QueryHelp:
    """Parse untrusted provider help output."""

    payload = parse_plan_payload(raw_help)
    try:
        return QueryHelp.model_validate(payload)
    except ValidationError as exc:
        msg = format_pydantic_error(exc).replace("QueryPlan", "QueryHelp")
        raise PlanValidationError(msg) from exc


def get_query_help_json_schema() -> dict[str, Any]:
    """Return the provider-facing JSON schema for strict query-help output."""

    schema = QueryHelp.model_json_schema()
    suggestion_schema = schema.get("$defs", {}).get("QueryHelpSuggestion", {})
    properties = suggestion_schema.get("properties", {})
    if isinstance(properties, dict):
        properties.pop("plan", None)
    return schema


def validate_query_help(
    help_result: QueryHelp,
    *,
    capabilities: CapabilitiesSnapshot,
    registry: CatalogRegistry = default_registry,
    permissions: Sequence[str] | None = None,
    require_plans: bool = False,
) -> QueryHelp:
    """Validate provider help against visible capabilities metadata."""

    resource_index = index_resource_references(capabilities)
    permission_set = tuple(permissions or ())
    valid_suggestions: list[QueryHelpSuggestion] = []
    errors: list[str] = []
    for suggestion in help_result.suggestions:
        try:
            normalized_suggestion = validate_query_help_suggestion(
                suggestion,
                resource_index=resource_index,
                registry=registry,
                permissions=permission_set,
                require_plan=require_plans,
            )
        except PlanValidationError as exc:
            errors.append(str(exc))
            continue
        valid_suggestions.append(normalized_suggestion)

    if valid_suggestions or not help_result.suggestions:
        return QueryHelp(
            answer=help_result.answer,
            suggestions=tuple(valid_suggestions),
            notes=help_result.notes,
        )

    error_summary = "; ".join(errors[:3])
    raise PlanValidationError(error_summary or "QueryHelp suggestions were invalid.")


def validate_query_help_suggestion(
    suggestion: QueryHelpSuggestion,
    *,
    resource_index: Mapping[str, CapabilityResource],
    registry: CatalogRegistry = default_registry,
    permissions: Sequence[str] | None = None,
    require_plan: bool = False,
) -> QueryHelpSuggestion:
    """Validate one provider suggestion against visible capabilities."""

    resource = resource_index.get(suggestion.resource_name.casefold())
    if resource is None:
        msg = (
            "QueryHelp suggestion referenced unknown capabilities resource "
            f"{suggestion.resource_name!r}."
        )
        raise PlanValidationError(msg)

    suggestion = normalize_suggestion_references(suggestion, resource)
    validate_suggestion_question_is_safe(suggestion.question)
    validate_suggestion_respects_scope(suggestion, resource)
    validate_references(
        suggestion.fields,
        allowed={field["name"] for field in resource.get("fields", [])},
        label="field",
        resource_name=suggestion.resource_name,
    )
    validate_references(
        suggestion.metrics,
        allowed={metric["name"] for metric in resource.get("metrics", [])},
        label="metric",
        resource_name=suggestion.resource_name,
    )
    validate_references(
        suggestion.date_fields,
        allowed={field["name"] for field in resource.get("date_fields", [])},
        label="date field",
        resource_name=suggestion.resource_name,
    )
    return validate_suggestion_plan(
        suggestion,
        resource=resource,
        registry=registry,
        permissions=permissions,
        require_plan=require_plan,
    )


def validate_suggestion_plan(
    suggestion: QueryHelpSuggestion,
    *,
    resource: CapabilityResource,
    registry: CatalogRegistry,
    permissions: Sequence[str] | None,
    require_plan: bool,
) -> QueryHelpSuggestion:
    """Validate or locally synthesize an executable plan for a suggestion."""

    raw_plan = suggestion.plan
    if raw_plan is None:
        if not require_plan:
            return suggestion
        raw_plan = build_suggestion_plan_payload(suggestion, resource=resource)

    validated_plan = parse_and_validate_query_plan(
        raw_plan,
        registry=registry,
        permissions=permissions,
    )
    if validated_plan.resource != resource["name"]:
        msg = (
            f"QueryHelp suggestion for resource {suggestion.resource_name!r} "
            f"included a plan for resource {validated_plan.resource!r}."
        )
        raise PlanValidationError(msg)
    validate_plan_uses_capabilities(validated_plan, resource=resource)

    return suggestion.model_copy(
        update={"plan": validated_plan.model_dump(mode="json")}
    )


def build_suggestion_plan_payload(
    suggestion: QueryHelpSuggestion,
    *,
    resource: CapabilityResource,
) -> dict[str, Any]:
    """Build a conservative QueryPlan from validated suggestion references."""

    metric_lookup = {metric["name"]: metric for metric in resource.get("metrics", [])}
    field_lookup = {field["name"]: field for field in resource.get("fields", [])}
    metrics = [
        metric_lookup[name] for name in suggestion.metrics if name in metric_lookup
    ]

    if metrics:
        return build_aggregate_suggestion_plan(
            suggestion,
            resource=resource,
            field_lookup=field_lookup,
            metrics=metrics,
        )
    return build_list_suggestion_plan(
        suggestion,
        resource=resource,
        field_lookup=field_lookup,
    )


def build_aggregate_suggestion_plan(
    suggestion: QueryHelpSuggestion,
    *,
    resource: CapabilityResource,
    field_lookup: Mapping[str, Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build an aggregate plan from suggestion metric references."""

    group_by: list[dict[str, str]] = []
    if suggestion.date_fields:
        date_field = suggestion.date_fields[0]
        group_by.append({"field": date_field, "date_trunc": "month"})
    else:
        group_by.extend(
            {"field": field_name}
            for field_name in suggestion.fields[:2]
            if field_lookup.get(field_name, {}).get("can_group")
        )

    metric_payloads = [
        {
            "name": metric["name"],
            "op": metric["op"],
            "field": metric["field"],
        }
        for metric in metrics
    ]
    first_metric_name = metric_payloads[0]["name"]
    order_by: list[dict[str, str]] = []
    if suggestion.date_fields and group_by:
        order_by.append({"field": group_by[0]["field"], "direction": "asc"})
    else:
        order_by.append({"metric": first_metric_name, "direction": "desc"})

    visualization = build_aggregate_suggestion_visualization(
        group_by=group_by,
        metric_name=first_metric_name,
        has_date_field=bool(suggestion.date_fields),
    )
    return {
        "resource": resource["name"],
        "intent": "aggregate",
        "filters": [],
        "group_by": group_by,
        "metrics": metric_payloads,
        "select": [],
        "order_by": order_by,
        "limit": 50,
        "visualization": visualization,
    }


def build_aggregate_suggestion_visualization(
    *,
    group_by: Sequence[Mapping[str, str]],
    metric_name: str,
    has_date_field: bool,
) -> dict[str, str]:
    """Return a valid visualization hint for a synthesized aggregate plan."""

    if not group_by:
        return {"type": "metric", "y": metric_name}
    chart_type = "line" if has_date_field else "bar"
    return {"type": chart_type, "x": group_by[0]["field"], "y": metric_name}


def build_list_suggestion_plan(
    suggestion: QueryHelpSuggestion,
    *,
    resource: CapabilityResource,
    field_lookup: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a list plan from suggestion field references."""

    select = [
        field_name
        for field_name in suggestion.fields
        if field_lookup.get(field_name, {}).get("can_select")
    ]
    if not select:
        select = [
            field["name"]
            for field in resource.get("fields", [])
            if field.get("can_select")
        ][:3]
    if not select:
        msg = (
            f"QueryHelp suggestion for resource {suggestion.resource_name!r} "
            "does not reference selectable fields or metrics."
        )
        raise PlanValidationError(msg)

    return {
        "resource": resource["name"],
        "intent": "list",
        "filters": [],
        "group_by": [],
        "metrics": [],
        "select": select[:8],
        "order_by": [],
        "limit": 50,
        "visualization": {"type": "table"},
    }


def validate_plan_uses_capabilities(
    plan: QueryPlan,
    *,
    resource: CapabilityResource,
) -> None:
    """Validate a suggestion plan against the visible capability resource."""

    allowed_fields = {field["name"] for field in resource.get("fields", [])}
    used_fields = set(plan.select)
    used_fields.update(filter_spec.field for filter_spec in plan.filters)
    used_fields.update(group.field for group in plan.group_by)
    used_fields.update(
        order_spec.field for order_spec in plan.order_by if order_spec.field is not None
    )
    validate_references(
        tuple(sorted(used_fields)),
        allowed=allowed_fields,
        label="plan field",
        resource_name=resource["name"],
    )

    date_bucket_fields = {
        group.field for group in plan.group_by if group.date_trunc is not None
    }
    validate_references(
        tuple(sorted(date_bucket_fields)),
        allowed={field["name"] for field in resource.get("date_fields", [])},
        label="plan date field",
        resource_name=resource["name"],
    )

    metric_names = {metric.name for metric in plan.metrics}
    validate_references(
        tuple(sorted(metric_names)),
        allowed={metric["name"] for metric in resource.get("metrics", [])},
        label="plan metric",
        resource_name=resource["name"],
    )


def normalize_suggestion_references(
    suggestion: QueryHelpSuggestion,
    resource: CapabilityResource,
) -> QueryHelpSuggestion:
    """Canonicalize provider references from visible labels to exact names."""

    return QueryHelpSuggestion(
        question=suggestion.question,
        resource_name=resource["name"],
        fields=canonicalize_references(
            suggestion.fields,
            items=resource.get("fields", []),
        ),
        metrics=canonicalize_references(
            suggestion.metrics,
            items=resource.get("metrics", []),
        ),
        date_fields=canonicalize_references(
            suggestion.date_fields,
            items=resource.get("date_fields", []),
        ),
        plan=suggestion.plan,
        why=suggestion.why,
    )


def canonicalize_references(
    references: Sequence[str],
    *,
    items: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Map provider references by name or label while preserving order."""

    canonical_index: dict[str, str] = {}
    for item in items:
        name = item.get("name")
        label = item.get("label")
        if isinstance(name, str):
            canonical_index[name.casefold()] = name
            if isinstance(label, str):
                canonical_index[label.casefold()] = name

    normalized: list[str] = []
    seen: set[str] = set()
    for reference in references:
        canonical = canonical_index.get(reference.casefold(), reference)
        if canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return tuple(normalized)


def build_deterministic_query_help(
    *,
    capabilities: CapabilitiesSnapshot,
    question: str | None = None,
    suggestion_count: int | None = None,
) -> QueryHelp:
    """Build query-help suggestions from deterministic capabilities examples."""

    desired_count = suggestion_count or requested_suggestion_count(question or "")
    suggestions: list[QueryHelpSuggestion] = []
    for resource in capabilities.get("resources", []):
        for example in resource.get("examples", []):
            suggestions.append(
                QueryHelpSuggestion(
                    question=example,
                    resource_name=resource["name"],
                    why="Generated from registered AskLens capabilities metadata.",
                )
            )
            if len(suggestions) >= desired_count:
                break
        if len(suggestions) >= desired_count:
            break

    answer = capabilities.get("summary") or "AskLens query guidance is available."
    notes = (
        "Suggestions are based only on resources and fields visible to this request.",
        "AskLens will still validate every generated query plan before execution.",
    )
    return QueryHelp(answer=answer, suggestions=tuple(suggestions), notes=notes)


def index_resource_references(
    capabilities: CapabilitiesSnapshot,
) -> dict[str, CapabilityResource]:
    """Index visible resources by exact names, labels, and synonyms."""

    index: dict[str, CapabilityResource] = {}
    for resource in capabilities.get("resources", []):
        references = [
            resource["name"],
            resource["label"],
            *resource.get("synonyms", []),
        ]
        for reference in references:
            index[reference.casefold()] = resource
    return index


def validate_suggestion_respects_scope(
    suggestion: QueryHelpSuggestion,
    resource: CapabilityResource,
) -> None:
    """Reject help suggestions that imply access outside a single visible scope."""

    scope = resource.get("scope")
    if scope is None or scope["level"] != "single" or "kind" not in scope:
        return

    scope_kind = scope["kind"]
    if is_single_scope_resource(resource, scope=scope):
        msg = (
            f"QueryHelp suggestion for resource {suggestion.resource_name!r} "
            f"targets the single visible {humanize_scope_kind(scope_kind)}. "
            "Suggest questions over in-scope operational resources instead."
        )
        raise PlanValidationError(msg)

    fields_by_name = {field["name"]: field for field in resource.get("fields", [])}
    blocked_fields = [
        field_name
        for field_name in suggestion.fields
        if fields_by_name.get(field_name, {}).get("scope_dimension")
        or is_scope_dimension_field(
            field_name=field_name,
            field_label=fields_by_name.get(field_name, {}).get("label", field_name),
            scope_kind=scope_kind,
        )
    ]
    if blocked_fields:
        blocked_display = ", ".join(sorted(blocked_fields))
        msg = (
            f"QueryHelp suggestion for resource {suggestion.resource_name!r} "
            f"references {humanize_scope_kind(scope_kind)} scope fields for a "
            f"single visible {humanize_scope_kind(scope_kind)}: {blocked_display}."
        )
        raise PlanValidationError(msg)

    if question_implies_multi_scope(suggestion.question, scope_kind=scope_kind):
        msg = (
            f"QueryHelp suggestion for resource {suggestion.resource_name!r} "
            f"implies access across {pluralize_scope_kind(scope_kind)}, but this "
            f"request is scoped to a single visible "
            f"{humanize_scope_kind(scope_kind)}."
        )
        raise PlanValidationError(msg)


def question_implies_multi_scope(question: str, *, scope_kind: str) -> bool:
    """Return whether question wording implies cross-scope access."""

    kind = re.escape(humanize_scope_kind(scope_kind).lower())
    plural = re.escape(pluralize_scope_kind(scope_kind).lower())
    lower_question = question.lower()
    patterns = [
        rf"\bacross\s+(?:all\s+)?{plural}\b",
        rf"\bcompare\s+(?:all\s+)?{plural}\b",
        rf"\bbetween\s+{plural}\b",
        rf"\bby\s+{kind}\b",
        rf"\bby\s+{plural}\b",
        rf"\bper\s+{kind}\b",
        rf"\bper\s+{plural}\b",
        rf"\bgroup(?:ed|ing)?\s+by\s+{kind}\b",
        rf"\bgroup(?:ed|ing)?\s+by\s+{plural}\b",
        r"\bacross\s+(?:all\s+)?scopes\b",
        r"\bcross[-\s]?scope\b",
    ]
    return any(re.search(pattern, lower_question) for pattern in patterns)


def validate_references(
    references: Sequence[str],
    *,
    allowed: set[str],
    label: str,
    resource_name: str,
) -> None:
    """Validate suggested catalog references against one resource."""

    unknown = set(references) - allowed
    if unknown:
        unknown_display = ", ".join(sorted(unknown))
        msg = (
            f"QueryHelp suggestion for resource {resource_name!r} referenced "
            f"unknown {label}s: {unknown_display}."
        )
        raise PlanValidationError(msg)


def validate_suggestion_question_is_safe(question: str) -> None:
    """Reject query-help suggestions that ask for mutations or SQL."""

    tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
    if "sql" in tokens:
        raise PlanValidationError("QueryHelp suggestions must not mention SQL.")
    if re.search(r"(?<!\w)(['\"])[^'\"]{2,}\1", question):
        raise PlanValidationError(
            "QueryHelp suggestions must not include literal sample values."
        )
    if re.search(
        r"\b[a-z0-9]+(?:_[a-z0-9]+)+_(day|week|month|quarter|year)\b",
        question.lower(),
    ):
        raise PlanValidationError(
            "QueryHelp suggestions must not mention generated date-bucket aliases."
        )
    blocked = tokens & BLOCKED_SUGGESTION_ACTIONS
    if blocked:
        blocked_display = ", ".join(sorted(blocked))
        msg = f"QueryHelp suggestions must be read-only; blocked: {blocked_display}."
        raise PlanValidationError(msg)
