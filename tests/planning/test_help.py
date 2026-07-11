"""Tests for provider-backed query-help generation."""

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from django_asklens.exceptions import PlanValidationError
from django_asklens.llms import LLMMessage
from django_asklens.planning.help import (
    build_deterministic_query_help,
    build_query_help,
    parse_query_help,
)


class HelpProvider:
    """Provider double for query-help tests."""

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
    """Return visible capabilities with one resource for query-help tests."""

    return {
        "summary": "You can query Orders.",
        "query_patterns": [],
        "limitations": [],
        "examples": ["Show count of Orders by Status"],
        "resources": [
            {
                "name": "orders",
                "label": "Orders",
                "description": "Orders.",
                "synonyms": [],
                "default_date_field": "created_at",
                "fields": [
                    {
                        "name": "status",
                        "label": "Status",
                        "type": "string",
                        "relation_depth": 0,
                        "can_filter": True,
                        "can_select": True,
                        "can_group": True,
                        "can_order": True,
                        "can_date_bucket": False,
                    },
                    {
                        "name": "created_at",
                        "label": "Created date",
                        "type": "datetime",
                        "relation_depth": 0,
                        "can_filter": True,
                        "can_select": True,
                        "can_group": True,
                        "can_order": True,
                        "can_date_bucket": True,
                    },
                ],
                "metrics": [
                    {
                        "name": "order_count",
                        "label": "Order count",
                        "op": "count",
                        "field": "status",
                    }
                ],
                "date_fields": [
                    {
                        "name": "created_at",
                        "label": "Created date",
                        "type": "datetime",
                        "relation_depth": 0,
                        "can_filter": True,
                        "can_select": True,
                        "can_group": True,
                        "can_order": True,
                        "can_date_bucket": True,
                    }
                ],
                "examples": ["Show count of Orders by Status"],
                "guidance": [],
            }
        ],
    }


def test_build_query_help_uses_provider_and_validates_references() -> None:
    """Provider-backed help returns validated suggestions from visible metadata."""

    provider = HelpProvider(
        {
            "answer": "You can ask order count and trend questions.",
            "suggestions": [
                {
                    "question": "Show order count by status",
                    "resource_name": "orders",
                    "fields": ["status"],
                    "metrics": ["order_count"],
                    "date_fields": [],
                    "why": "Groups the registered order count metric by status.",
                },
                {
                    "question": "Trend order count by month using created date",
                    "resource_name": "orders",
                    "fields": [],
                    "metrics": ["order_count"],
                    "date_fields": ["created_at"],
                },
            ],
            "notes": ["Only visible fields are used."],
        }
    )

    result = build_query_help(
        "Help me write order questions",
        provider=provider,
        capabilities=capabilities_payload(),
    )

    assert result.answer == "You can ask order count and trend questions."
    assert result.suggestions[0].resource_name == "orders"
    assert result.suggestions[0].fields == ("status",)
    assert result.suggestions[1].date_fields == ("created_at",)
    assert provider.schema is not None
    assert provider.schema["title"] == "QueryHelp"
    assert provider.messages is not None
    prompt_text = "\n".join(message["content"] for message in provider.messages)
    assert "Visible capabilities metadata" in prompt_text
    assert "orders" in prompt_text
    assert "facilities/accounts/tenants" not in prompt_text


def test_build_query_help_rejects_unknown_references() -> None:
    """Provider suggestions cannot mention fields outside capabilities."""

    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "List orders with private notes",
                    "resource_name": "orders",
                    "fields": ["private_notes"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="private_notes"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=capabilities_payload(),
        )


def test_build_query_help_rejects_sql_or_mutation_suggestions() -> None:
    """Query help must remain read-only and natural-language only."""

    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Delete orders by status",
                    "resource_name": "orders",
                    "fields": ["status"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="read-only"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=capabilities_payload(),
        )


def test_build_query_help_rejects_single_scope_resource_suggestions() -> None:
    """Live help should not suggest plural scoped-entity questions."""

    payload = capabilities_payload()
    payload["resources"] = [
        {
            "name": "facilities",
            "label": "Facilities",
            "description": "Visible facilities.",
            "synonyms": [],
            "default_date_field": None,
            "scope": {
                "level": "single",
                "kind": "facility",
                "guidance": "Visible rows are scoped to one facility.",
            },
            "fields": [
                {
                    "name": "name",
                    "label": "Facility name",
                    "type": "string",
                    "relation_depth": 0,
                    "can_filter": True,
                    "can_select": True,
                    "can_group": True,
                    "can_order": True,
                    "can_date_bucket": False,
                }
            ],
            "metrics": [],
            "date_fields": [],
            "examples": [],
            "guidance": [],
        }
    ]
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "List Facilities with Facility name",
                    "resource_name": "facilities",
                    "fields": ["name"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="single visible facility"):
        build_query_help(
            "Help me write facility questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_arbitrarily_named_scope_resource() -> None:
    """Scope-resource validation should not depend on resource naming."""

    payload = capabilities_payload()
    payload["resources"] = [
        {
            "name": "locations",
            "label": "Studios",
            "description": "Visible studios.",
            "synonyms": [],
            "default_date_field": None,
            "scope": {
                "level": "single",
                "kind": "gym",
                "guidance": "Visible rows are scoped to one gym.",
            },
            "scope_resource": True,
            "fields": [
                {
                    "name": "display_name",
                    "label": "Display name",
                    "type": "string",
                    "relation_depth": 0,
                    "can_filter": True,
                    "can_select": True,
                    "can_group": True,
                    "can_order": True,
                    "can_date_bucket": False,
                }
            ],
            "metrics": [],
            "date_fields": [],
            "examples": [],
            "guidance": [],
        }
    ]
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "List Studios with Display name",
                    "resource_name": "locations",
                    "fields": ["display_name"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="single visible gym"):
        build_query_help(
            "Help me write studio questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_single_scope_comparison_wording() -> None:
    """Help suggestions must not imply multi-scope access for single scopes."""

    payload = capabilities_payload()
    resource = payload["resources"][0]
    resource["scope"] = {
        "level": "single",
        "kind": "facility",
        "guidance": "Visible rows are scoped to one facility.",
    }
    resource["fields"].append(
        {
            "name": "facility.name",
            "label": "Facility",
            "type": "string",
            "relation_depth": 1,
            "can_filter": True,
            "can_select": True,
            "can_group": True,
            "can_order": True,
            "can_date_bucket": False,
        }
    )
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Compare order count across facilities",
                    "resource_name": "orders",
                    "fields": [],
                    "metrics": ["order_count"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="single visible facility"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_explicit_scope_dimension_fields() -> None:
    """Scope fields do not need facility/account/tenant naming to be blocked."""

    payload = capabilities_payload()
    resource = payload["resources"][0]
    resource["scope"] = {
        "level": "single",
        "kind": "gym",
        "guidance": "Visible rows are scoped to one gym.",
    }
    resource["fields"].append(
        {
            "name": "home_box.label",
            "label": "Home box",
            "type": "string",
            "relation_depth": 1,
            "can_filter": True,
            "can_select": True,
            "can_group": True,
            "can_order": True,
            "can_date_bucket": False,
            "scope_dimension": True,
        }
    )
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Show order count by home box",
                    "resource_name": "orders",
                    "fields": ["home_box.label"],
                    "metrics": ["order_count"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="scope fields"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_single_scope_dimension_fields() -> None:
    """Provider suggestions cannot use facility dimensions for one facility."""

    payload = capabilities_payload()
    resource = payload["resources"][0]
    resource["scope"] = {
        "level": "single",
        "kind": "facility",
        "guidance": "Visible rows are scoped to one facility.",
    }
    resource["fields"].append(
        {
            "name": "facility.name",
            "label": "Facility",
            "type": "string",
            "relation_depth": 1,
            "can_filter": True,
            "can_select": True,
            "can_group": True,
            "can_order": True,
            "can_date_bucket": False,
        }
    )
    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Show order count by facility",
                    "resource_name": "orders",
                    "fields": ["facility.name"],
                    "metrics": ["order_count"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="scope fields"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=payload,
        )


def test_build_query_help_rejects_generated_date_bucket_aliases() -> None:
    """Help suggestions should not teach users invalid result-key aliases."""

    provider = HelpProvider(
        {
            "answer": "Try this.",
            "suggestions": [
                {
                    "question": "Trend order count by created_at_month",
                    "resource_name": "orders",
                    "metrics": ["order_count"],
                    "date_fields": ["created_at"],
                }
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="date-bucket aliases"):
        build_query_help(
            "Help me write order questions",
            provider=provider,
            capabilities=capabilities_payload(),
        )


def test_parse_query_help_rejects_extra_keys() -> None:
    """QueryHelp provider output is strict."""

    with pytest.raises(PlanValidationError, match="raw_sql"):
        parse_query_help({"answer": "Try this.", "raw_sql": "select 1"})


def test_deterministic_query_help_uses_capabilities_examples() -> None:
    """Offline help falls back to deterministic examples from capabilities."""

    result = build_deterministic_query_help(capabilities=capabilities_payload())

    assert result.answer == "You can query Orders."
    assert result.suggestions[0].question == "Show count of Orders by Status"
    assert result.suggestions[0].resource_name == "orders"
