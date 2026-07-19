"""Helpers for the optional Django admin AskLens query page."""

from typing import Any

from django_asklens.models import SemanticQueryRun
from django_asklens.querying import execute_asklens_query_request


def execute_admin_query(
    request,
    *,
    question: str,
) -> tuple[dict[str, Any] | None, SemanticQueryRun | None, str, bool]:
    """Execute one AskLens request from Django admin."""

    outcome = execute_asklens_query_request(
        request,
        question=question,
        debug=False,
        include_visualization=True,
    )
    if outcome.response_type == "error":
        return None, outcome.run, str(outcome.payload.get("error", "")), False
    return outcome.payload, outcome.run, "", False


def build_admin_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return a template-friendly representation of an AskLens response."""

    if result.get("response_type") == "capabilities":
        return build_admin_capabilities_result(result)
    return build_admin_query_result(result)


def build_admin_query_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return a template-friendly representation of query rows."""

    columns = result["columns"]
    return {
        "response_type": "query",
        "columns": columns,
        "rows": [
            {"cells": [row.get(column["key"], "") for column in columns]}
            for row in result["data"]
        ],
        "row_count": result["row_count"],
        "duration_ms": result["duration_ms"],
        "visualization": result.get("visualization"),
    }


def build_admin_capabilities_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return a template-friendly representation of query help."""

    capabilities = result.get("capabilities") or {}
    query_help = result.get("query_help") or {}
    suggestions = query_help.get("suggestions") or []
    return {
        "response_type": "capabilities",
        "answer": query_help.get("answer") or capabilities.get("summary") or "",
        "summary": capabilities.get("summary", ""),
        "query_help_source": result.get("query_help_source", ""),
        "query_help_error": result.get("query_help_error", ""),
        "suggestions": [
            {
                "question": suggestion.get("question", ""),
                "resource_name": suggestion.get("resource_name", ""),
                "why": suggestion.get("why", ""),
            }
            for suggestion in suggestions
        ],
    }
