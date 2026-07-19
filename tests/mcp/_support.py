"""Shared helpers for MCP adapter tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def aware_datetime(year: int, month: int, day: int) -> datetime:
    """Return a UTC-aware datetime for fixtures."""

    return datetime(year, month, day, 12, 0, tzinfo=UTC)


def valid_aggregate_plan() -> dict[str, Any]:
    """Return a deterministic aggregate QueryPlan payload."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "status", "y": "order_count"},
    }


def sensitive_list_plan() -> dict[str, Any]:
    """Return a plan that requires the customer PII permission."""

    return {
        "resource": "orders",
        "intent": "list",
        "select": ["customer.email"],
        "limit": 10,
        "visualization": {"type": "table"},
    }
