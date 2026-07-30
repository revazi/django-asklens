"""Planner orchestration for untrusted provider QueryPlan output."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.exceptions import PlanValidationError
from django_asklens.llms.base import LLMMessage, LLMProvider
from django_asklens.llms.factory import get_llm_provider
from django_asklens.planning.prompts import (
    build_planner_catalog,
    build_planner_messages,
)
from django_asklens.planning.schemas import (
    PlanBaseModel,
    PresentationSpec,
    QueryPlan,
    format_pydantic_error,
    parse_plan_payload,
)
from django_asklens.planning.validation import PlanLimits, validate_query_plan


@dataclass(frozen=True, slots=True)
class PlannerRequest:
    """Inputs needed to request a QueryPlan from a provider."""

    question: str
    messages: tuple[LLMMessage, ...]
    schema: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class PlannerResult:
    """Result of a planner/provider round-trip."""

    question: str
    plan: QueryPlan
    presentation: PresentationSpec | None = None


class PlannerProviderResponse(PlanBaseModel):
    """Strict provider envelope separating plans from presentation metadata."""

    query_plan: QueryPlan
    presentation: PresentationSpec | None = None


def plan_question(
    question: str,
    *,
    provider: LLMProvider | None = None,
    registry: CatalogRegistry = default_registry,
    limits: PlanLimits | None = None,
    permissions: Iterable[str] | None = None,
) -> PlannerResult:
    """Ask a provider for a QueryPlan and validate it before returning."""

    permission_set = frozenset(permissions or ())
    request = build_planner_request(
        question=question,
        registry=registry,
        permissions=permission_set,
    )
    selected_provider = provider or get_llm_provider()
    provider_payload = selected_provider.complete_json(
        messages=request.messages,
        schema=request.schema,
    )
    response = parse_planner_provider_response(provider_payload)
    plan = validate_query_plan(
        response.query_plan,
        registry=registry,
        limits=limits,
        permissions=permission_set,
    )
    return PlannerResult(
        question=question,
        plan=plan,
        presentation=response.presentation,
    )


def build_planner_request(
    *,
    question: str,
    registry: CatalogRegistry = default_registry,
    permissions: Iterable[str] | None = None,
) -> PlannerRequest:
    """Build a provider request containing safe catalog metadata and schema."""

    catalog = build_planner_catalog(registry, permissions=permissions)
    return PlannerRequest(
        question=question,
        messages=build_planner_messages(question=question, catalog=catalog),
        schema=PlannerProviderResponse.model_json_schema(),
    )


def parse_planner_provider_response(
    raw_response: str | bytes | Mapping[str, Any],
) -> PlannerProviderResponse:
    """Parse an untrusted provider plan/presentation envelope."""

    try:
        return PlannerProviderResponse.model_validate(parse_plan_payload(raw_response))
    except ValidationError as exc:
        msg = format_pydantic_error(exc).replace("QueryPlan", "PlannerProviderResponse")
        raise PlanValidationError(msg) from exc
