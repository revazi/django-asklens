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
from django_asklens.exceptions import PlanValidationError
from django_asklens.llms.base import LLMMessage, LLMProvider
from django_asklens.llms.factory import get_llm_provider
from django_asklens.planning.prompts import stable_json_dumps
from django_asklens.planning.schemas import (
    PLAN_MODEL_CONFIG,
    PlanBaseModel,
    format_pydantic_error,
    parse_plan_payload,
    validate_non_empty_string,
)

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
metric, and date_field names from the metadata. Do not simply copy generated
examples from the metadata when better provider-generated suggestions are possible.
If a resource scope has level="single", suggestions must be phrased within
that single visible scope. Do not suggest comparing, grouping, filtering, or
trending across any scope dimension unless the resource scope allows multiple
or all scopes and the scope-dimension field is visible.
Do not suggest internal result-key aliases such as "start_date_month"; say
"by month using start date" in the natural-language question instead.
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
    help_result = validate_query_help(
        parse_query_help(payload),
        capabilities=capabilities,
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
    """Return the JSON schema for strict query-help output."""

    return QueryHelp.model_json_schema()


def validate_query_help(
    help_result: QueryHelp,
    *,
    capabilities: CapabilitiesSnapshot,
) -> QueryHelp:
    """Validate provider help against visible capabilities metadata."""

    resource_index = index_resource_references(capabilities)
    valid_suggestions: list[QueryHelpSuggestion] = []
    errors: list[str] = []
    for suggestion in help_result.suggestions:
        try:
            normalized_suggestion = validate_query_help_suggestion(
                suggestion,
                resource_index=resource_index,
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
    return suggestion


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
