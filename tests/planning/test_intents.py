"""Tests for question intent routing."""

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from django_asklens.exceptions import PlanValidationError
from django_asklens.llms import LLMMessage
from django_asklens.planning.intents import (
    filter_capabilities_for_intent,
    is_capabilities_fallback_question,
    parse_question_intent,
    route_question_intent,
)


class IntentProvider:
    """Provider double for semantic intent routing tests."""

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


def capabilities_payload() -> dict[str, Any]:
    """Return a minimal visible capabilities payload for routing tests."""

    return {
        "summary": "You can query 2 resources.",
        "query_patterns": [],
        "limitations": [],
        "examples": ["Show order count by status", "Show payment amount by status"],
        "resources": [
            {
                "name": "orders",
                "label": "Orders",
                "description": "Orders.",
                "synonyms": [],
                "default_date_field": "created_at",
                "fields": [],
                "metrics": [],
                "date_fields": [],
                "examples": ["Show order count by status"],
                "guidance": [],
            },
            {
                "name": "payment_attempts",
                "label": "Payment attempts",
                "description": "Payments.",
                "synonyms": [],
                "default_date_field": "created_at",
                "fields": [],
                "metrics": [],
                "date_fields": [],
                "examples": ["Show payment amount by status"],
                "guidance": [],
            },
        ],
    }


def test_fallback_capabilities_detector_is_compact_and_conservative() -> None:
    """Fallback handles obvious help questions without becoming the main router."""

    assert is_capabilities_fallback_question("What can I query?") is True
    assert is_capabilities_fallback_question("what fields are available") is True
    assert is_capabilities_fallback_question("List queryable resources") is True
    assert is_capabilities_fallback_question("Show orders by status") is False
    assert is_capabilities_fallback_question("List member contact emails") is False


def test_provider_backed_semantic_routing_selects_capabilities_resource() -> None:
    """Semantic routing can select capability intent and a visible resource."""

    provider = IntentProvider(
        {
            "intent": "capabilities",
            "resource_names": ["payment_attempts"],
            "sections": ["metrics", "examples"],
            "confidence": 0.91,
        }
    )
    capabilities = capabilities_payload()

    result = route_question_intent(
        "Which payment metrics can I ask about?",
        provider=provider,
        capabilities=capabilities,
    )
    filtered = filter_capabilities_for_intent(capabilities, result.intent)

    assert result.source == "semantic_provider"
    assert result.intent.intent == "capabilities"
    assert result.intent.resource_names == ("payment_attempts",)
    assert [resource["name"] for resource in filtered["resources"]] == [
        "payment_attempts"
    ]
    assert provider.schema is not None
    assert provider.schema["title"] == "QuestionIntent"
    assert provider.messages is not None
    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert "payment_attempts" in prompt_text
    assert "Visible capabilities metadata" in prompt_text


def test_provider_backed_semantic_routing_can_choose_query_intent() -> None:
    """Actual data requests should continue to the normal QueryPlan path."""

    provider = IntentProvider({"intent": "query", "confidence": 0.94})

    result = route_question_intent(
        "Show orders by status",
        provider=provider,
        capabilities=capabilities_payload(),
    )

    assert result.source == "semantic_provider"
    assert result.intent.intent == "query"


def test_question_intent_rejects_unknown_resources() -> None:
    """Provider-selected capability resources must already be visible."""

    provider = IntentProvider(
        {
            "intent": "capabilities",
            "resource_names": ["private_invoices"],
            "confidence": 0.91,
        }
    )

    with pytest.raises(PlanValidationError, match="private_invoices"):
        route_question_intent(
            "What invoice fields can I query?",
            provider=provider,
            capabilities=capabilities_payload(),
        )


def test_parse_question_intent_rejects_extra_keys() -> None:
    """QuestionIntent provider output is strict JSON like QueryPlan output."""

    with pytest.raises(PlanValidationError, match="raw_sql"):
        parse_question_intent(
            {"intent": "capabilities", "confidence": 1, "raw_sql": "select 1"}
        )
