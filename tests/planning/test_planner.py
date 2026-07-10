"""Tests for planner/provider orchestration."""

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import LLMProviderError, PlanValidationError
from django_asklens.llms import DummyProvider, LLMMessage
from django_asklens.planning.planner import build_planner_request, plan_question
from tests.test_project.models import Order

QUESTION = "Show orders by status"


def valid_plan_payload() -> dict[str, object]:
    """Return a deterministic valid plan payload."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "status", "y": "order_count"},
    }


def build_registry() -> CatalogRegistry:
    """Return a registry with safe and hidden fields for prompt tests."""

    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        fields={
            "id": {"label": "Order ID"},
            "status": {"label": "Status"},
            "created_at": {"label": "Created date"},
            "customer.email": {"label": "Customer email", "sensitive": True},
            "internal_notes": {"label": "Internal notes", "llm_visible": False},
        },
        metrics=[Metric("order_count", op="count", field="id")],
    )
    return registry


class SpyProvider:
    """Provider test double that records messages and schema."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload
        self.messages: Sequence[LLMMessage] | None = None
        self.schema: Mapping[str, Any] | None = None

    def complete_json(
        self,
        *,
        messages: Sequence[LLMMessage],
        schema: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.messages = messages
        self.schema = schema
        return self.payload


def test_dummy_provider_returns_deterministic_plan() -> None:
    provider = DummyProvider(plans={QUESTION: valid_plan_payload()})

    result = plan_question(QUESTION, provider=provider, registry=build_registry())

    assert result.question == QUESTION
    assert result.plan.resource == "orders"
    assert result.plan.metrics[0].name == "order_count"


def test_dummy_provider_without_configured_plan_fails() -> None:
    provider = DummyProvider()

    with pytest.raises(LLMProviderError, match="no plan configured"):
        plan_question(QUESTION, provider=provider, registry=build_registry())


def test_planner_sends_safe_catalog_metadata_and_schema() -> None:
    provider = SpyProvider(valid_plan_payload())

    plan_question(QUESTION, provider=provider, registry=build_registry())

    assert provider.schema is not None
    assert provider.schema["title"] == "QueryPlan"
    assert provider.messages is not None

    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert QUESTION in prompt_text
    assert "status" in prompt_text
    assert "order_count" in prompt_text
    assert "start_date_month" in prompt_text
    assert "original group_by field name" in prompt_text
    assert "customer.email" not in prompt_text
    assert "internal_notes" not in prompt_text
    assert "test_project.Order" not in prompt_text


def test_build_planner_request_is_deterministic_and_safe() -> None:
    request = build_planner_request(question=QUESTION, registry=build_registry())
    prompt_text = "\n".join(message["content"] for message in request.messages)

    assert request.question == QUESTION
    assert request.schema["title"] == "QueryPlan"
    assert "Catalog metadata" in prompt_text
    assert "Never invent bucket aliases" in prompt_text
    assert "customer.email" not in prompt_text
    assert "internal_notes" not in prompt_text


def test_provider_output_is_always_validated() -> None:
    provider = DummyProvider(
        plans={
            QUESTION: {
                "resource": "orders",
                "intent": "delete",
                "raw_sql": "select * from orders",
            }
        }
    )

    with pytest.raises(PlanValidationError):
        plan_question(QUESTION, provider=provider, registry=build_registry())


def test_default_dummy_backend_does_not_make_live_calls() -> None:
    with pytest.raises(LLMProviderError, match="DummyProvider"):
        plan_question(QUESTION, registry=build_registry())
