"""Planner orchestration for untrusted provider QueryPlan output."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.llms.base import LLMMessage, LLMProvider
from django_asklens.llms.factory import get_llm_provider
from django_asklens.planning.prompts import (
    build_planner_catalog,
    build_planner_messages,
)
from django_asklens.planning.schemas import QueryPlan, get_query_plan_json_schema
from django_asklens.planning.validation import PlanLimits, parse_and_validate_query_plan


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
    plan = parse_and_validate_query_plan(
        provider_payload,
        registry=registry,
        limits=limits,
        permissions=permission_set,
    )
    return PlannerResult(question=question, plan=plan)


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
        schema=get_query_plan_json_schema(),
    )
