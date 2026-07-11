"""Question intent routing for query execution versus capability guidance."""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator

from django_asklens.catalog.capabilities import (
    CapabilitiesSnapshot,
    build_capabilities,
)
from django_asklens.exceptions import AskLensError, PlanValidationError
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
from django_asklens.settings import get_asklens_setting

QuestionIntentType = Literal["query", "capabilities"]
CapabilitySection = Literal[
    "resources",
    "fields",
    "metrics",
    "date_fields",
    "examples",
    "limitations",
]

DEFAULT_CAPABILITY_SECTIONS: tuple[CapabilitySection, ...] = (
    "resources",
    "fields",
    "metrics",
    "date_fields",
    "examples",
    "limitations",
)

FALLBACK_CAPABILITY_HINTS = {
    "available",
    "capabilities",
    "capability",
    "help",
    "queryable",
}
FALLBACK_CAPABILITY_TARGETS = {
    "ask",
    "data",
    "entities",
    "entity",
    "fields",
    "field",
    "metrics",
    "metric",
    "queries",
    "query",
    "resources",
    "resource",
}

INTENT_SYSTEM_PROMPT = """You route Django AskLens user questions.
Return only JSON matching the provided QuestionIntent schema.
Choose intent="capabilities" when the user asks what AskLens can query,
which resources/entities/fields/metrics are available, examples of questions,
or help using AskLens.
Choose intent="query" when the user asks for actual records, rows, counts,
totals, trends, filtered data, or aggregate results.
For capabilities requests, resource_names must use only resource names present
in the capabilities metadata. Omit resource_names for general help.
Do not invent resources, fields, metrics, permissions, SQL, or explanations.
""".strip()


class QuestionIntent(PlanBaseModel):
    """Structured routing decision for a user question."""

    model_config = PLAN_MODEL_CONFIG

    intent: QuestionIntentType
    resource_names: tuple[str, ...] = Field(default_factory=tuple)
    sections: tuple[CapabilitySection, ...] = Field(
        default_factory=lambda: DEFAULT_CAPABILITY_SECTIONS
    )
    confidence: float = Field(default=1, ge=0, le=1)

    @field_validator("resource_names")
    @classmethod
    def validate_resource_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Validate selected resource names."""

        return tuple(validate_non_empty_string(item, "resource name") for item in value)


@dataclass(frozen=True, slots=True)
class IntentRoutingResult:
    """Result of routing a user question."""

    question: str
    intent: QuestionIntent
    source: Literal["semantic_provider", "fallback", "default"]


def query_intent(*, confidence: float = 1) -> QuestionIntent:
    """Return the default query intent."""

    return QuestionIntent(intent="query", confidence=confidence)


def capabilities_intent(
    *,
    confidence: float = 1,
    resource_names: Sequence[str] = (),
    sections: Sequence[CapabilitySection] = DEFAULT_CAPABILITY_SECTIONS,
) -> QuestionIntent:
    """Return a capabilities intent."""

    return QuestionIntent(
        intent="capabilities",
        resource_names=tuple(resource_names),
        sections=tuple(sections),
        confidence=confidence,
    )


def route_question_intent(
    question: str,
    *,
    permissions: Iterable[str] | None = None,
    provider: LLMProvider | None = None,
    capabilities: CapabilitiesSnapshot | None = None,
) -> IntentRoutingResult:
    """Route a question to query execution or capability guidance.

    Obvious help/capability wording is routed locally before any provider call.
    This avoids spending a live LLM request just to decide that a user asked for
    examples or capabilities. Live/custom providers are still available for
    ambiguous questions that the local detector does not recognize.
    """

    permission_set = frozenset(permissions or ())
    visible_capabilities = (
        capabilities
        if capabilities is not None
        else build_capabilities(permissions=permission_set)
    )

    if is_capabilities_fallback_question(question):
        return IntentRoutingResult(
            question=question,
            intent=capabilities_intent(confidence=0.7),
            source="fallback",
        )

    if provider is not None or get_asklens_setting("LLM_BACKEND") != "dummy":
        try:
            intent = plan_question_intent(
                question,
                provider=provider,
                capabilities=visible_capabilities,
            )
        except AskLensError:
            if is_capabilities_fallback_question(question):
                return IntentRoutingResult(
                    question=question,
                    intent=capabilities_intent(confidence=0.5),
                    source="fallback",
                )
            return IntentRoutingResult(
                question=question,
                intent=query_intent(confidence=0.5),
                source="default",
            )
        return IntentRoutingResult(
            question=question,
            intent=validate_question_intent(intent, visible_capabilities),
            source="semantic_provider",
        )

    return IntentRoutingResult(
        question=question,
        intent=query_intent(),
        source="default",
    )


def plan_question_intent(
    question: str,
    *,
    provider: LLMProvider | None = None,
    capabilities: CapabilitiesSnapshot,
) -> QuestionIntent:
    """Ask a provider to classify a question using visible capabilities only."""

    selected_provider = provider or get_llm_provider()
    payload = selected_provider.complete_json(
        messages=build_intent_messages(question=question, capabilities=capabilities),
        schema=get_question_intent_json_schema(),
    )
    return parse_question_intent(payload)


def build_intent_messages(
    *,
    question: str,
    capabilities: CapabilitiesSnapshot,
) -> tuple[LLMMessage, ...]:
    """Build provider messages for strict intent classification."""

    return (
        {"role": "system", "content": INTENT_SYSTEM_PROMPT},
        {"role": "user", "content": question},
        {
            "role": "user",
            "content": "Visible capabilities metadata:\n"
            + stable_json_dumps(capabilities),
        },
    )


def parse_question_intent(
    raw_intent: str | bytes | Mapping[str, Any],
) -> QuestionIntent:
    """Parse untrusted provider intent output."""

    payload = parse_plan_payload(raw_intent)
    try:
        return QuestionIntent.model_validate(payload)
    except ValidationError as exc:
        msg = format_pydantic_error(exc).replace("QueryPlan", "QuestionIntent")
        raise PlanValidationError(msg) from exc


def get_question_intent_json_schema() -> dict[str, Any]:
    """Return the JSON schema for strict question-intent output."""

    return QuestionIntent.model_json_schema()


def validate_question_intent(
    intent: QuestionIntent,
    capabilities: CapabilitiesSnapshot,
) -> QuestionIntent:
    """Validate provider-selected resources against visible capabilities."""

    visible_resource_names = {
        resource["name"] for resource in capabilities.get("resources", [])
    }
    unknown = set(intent.resource_names) - visible_resource_names
    if unknown:
        unknown_display = ", ".join(sorted(unknown))
        msg = (
            "QuestionIntent referenced unknown capabilities resources: "
            f"{unknown_display}."
        )
        raise PlanValidationError(msg)
    return intent


def filter_capabilities_for_intent(
    capabilities: CapabilitiesSnapshot,
    intent: QuestionIntent,
) -> CapabilitiesSnapshot:
    """Return capabilities narrowed to provider-selected visible resources."""

    if not intent.resource_names:
        return capabilities

    selected = set(intent.resource_names)
    resources = [
        resource
        for resource in capabilities.get("resources", [])
        if resource["name"] in selected
    ]
    return {
        **capabilities,
        "summary": build_filtered_summary(resources),
        "resources": resources,
        "examples": [
            example for resource in resources for example in resource["examples"]
        ],
    }


def build_filtered_summary(resources: Sequence[Mapping[str, Any]]) -> str:
    """Return a summary for a filtered capabilities payload."""

    count = len(resources)
    if count == 0:
        return "No matching AskLens resources are queryable for this request."
    if count == 1:
        return "This capabilities answer is scoped to 1 queryable resource."
    return f"This capabilities answer is scoped to {count} queryable resources."


def is_capabilities_fallback_question(question: str) -> bool:
    """Return whether fallback routing should answer with capabilities.

    This is intentionally a compact signal check, not the main semantic
    solution. In live/custom provider mode, provider-backed strict intent
    classification handles semantic capabilities questions first.
    """

    tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
    if not tokens:
        return False
    if tokens == {"help"} or tokens == {"capabilities"}:
        return True
    if tokens & FALLBACK_CAPABILITY_HINTS and tokens & FALLBACK_CAPABILITY_TARGETS:
        return True
    if {"what", "can"}.issubset(tokens) and bool(tokens & {"ask", "query", "queries"}):
        return True
    if {"queries", "run"}.issubset(tokens) and tokens & {"can", "could"}:
        return True
    if {"questions", "ask"}.issubset(tokens) and tokens & {"can", "could"}:
        return True
    if tokens & {
        "example",
        "examples",
        "sample",
        "samples",
        "suggestion",
        "suggestions",
    } and tokens & {
        "ask",
        "queries",
        "query",
        "questions",
        "question",
    }:
        return True
    if (
        tokens & {"show", "give", "list", "suggest", "return"}
        and tokens
        & {
            "example",
            "examples",
            "queries",
            "query",
            "questions",
            "question",
            "sample",
            "samples",
            "suggestion",
            "suggestions",
        }
        and (
            tokens & {"can", "could"}
            or tokens & {"example", "examples", "sample", "samples"}
        )
    ):
        return True
    return (
        bool(tokens & {"which", "what"})
        and bool(tokens & {"fields", "metrics", "resources", "entities"})
        and bool(tokens & {"ask", "query", "queries", "available"})
    )
