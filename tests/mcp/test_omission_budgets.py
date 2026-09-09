"""MCP response row policy never substitutes for trusted execution budgets."""

import json
from unittest.mock import Mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from django_asklens.execution import execute_plan, runner
from django_asklens.mcp import asklens_execute_plan
from django_asklens.models import SemanticQueryRun
from tests.mcp._support import valid_aggregate_plan

pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]

QUESTION = "Show orders for synthetic-mcp-budget-82"
PRIVATE_FILTER = 1_823_456_789
PRIVATE_DIAGNOSTIC = "private-audit-failure-82"
ERROR = {
    "code": "asklens.budget.exceeded",
    "message": "The query plan exceeds an execution limit.",
}
ROW_POLICIES = [
    pytest.param(False, None, 100, id="default-omission"),
    pytest.param(True, False, 100, id="caller-omits"),
    pytest.param(False, True, 100, id="host-denies"),
    pytest.param(True, True, 0, id="zero-output-cap"),
]


def budget_plan() -> dict:
    """Two requested groups and two filters independently exercise the bounds."""

    plan = valid_aggregate_plan()
    plan["limit"] = 2
    plan["filters"] = [
        {"field": "id", "op": "neq", "value": PRIVATE_FILTER},
        {"field": "id", "op": "gte", "value": 0},
    ]
    return plan


def row_arguments(include_rows: bool | None) -> dict:
    """Exercise the real default when the caller does not specify row return."""

    return {} if include_rows is None else {"include_rows": include_rows}


@pytest.mark.parametrize("budget", ["MAX_ROWS", "MAX_FILTERS"])
@pytest.mark.parametrize("allow_rows,include_rows,row_cap", ROW_POLICIES)
@pytest.mark.parametrize(
    "audit_mode", ["disabled", "database", "custom", "failing-custom"]
)
def test_mcp_omission_or_output_cap_cannot_bypass_budget_rejection(
    budget: str,
    allow_rows: bool,
    include_rows: bool | None,
    row_cap: int,
    audit_mode: str,
    settings,
    registered_orders,
    order_data,
    mcp_request,
    monkeypatch,
) -> None:
    events = []

    def sink(event):
        events.append(event)
        if audit_mode == "failing-custom":
            raise RuntimeError(PRIVATE_DIAGNOSTIC)

    settings.DJANGO_ASKLENS.update(
        {
            budget: 1,
            "AUDIT_MODE": "custom" if audit_mode == "failing-custom" else audit_mode,
            "AUDIT_SINK": sink,
            "AUDIT_INCLUDE_CONTENT": False,
            "MCP_ALLOW_ROW_RETURN": allow_rows,
            "MCP_MAX_RETURNED_ROWS": row_cap,
        }
    )
    plan = budget_plan()
    facade = Mock(wraps=execute_plan)
    preparation = Mock(wraps=runner._prepare_query_plan)
    monkeypatch.setattr("django_asklens.querying.execute_plan", facade)
    monkeypatch.setattr(
        "django_asklens.execution.runner._prepare_query_plan", preparation
    )
    planners = []
    for name in ("plan_question", "plan_asklens_response", "route_question_intent"):
        trap = Mock(
            side_effect=AssertionError("Supplied MCP plan reached a provider/planner.")
        )
        monkeypatch.setattr(f"django_asklens.querying.{name}", trap)
        planners.append(trap)

    with CaptureQueriesContext(connection) as captured:
        payload = asklens_execute_plan(
            mcp_request, plan, question=QUESTION, **row_arguments(include_rows)
        )

    facade.assert_called_once_with(plan, request=mcp_request)
    preparation.assert_not_called()
    for planner in planners:
        planner.assert_not_called()
    expected = {
        "question": QUESTION,
        "status": "failed",
        "error": ERROR,
        "response_type": "error",
        "status_code": 400,
    }
    if audit_mode == "database":
        assert len(captured) == 1
        sql = captured[0]["sql"].strip().upper()
        assert sql.startswith('INSERT INTO "ASKLENS_SEMANTICQUERYRUN"')
        assert "TEST_PROJECT_ORDER" not in sql
        run = SemanticQueryRun.objects.get()
        expected["run_id"] = run.pk
        assert run.user == mcp_request.user
        assert run.question == "" and run.plan == {}
        assert run.status == "failed" and run.row_count == 0
        assert run.duration_ms is None
        assert run.error == f"{ERROR['code']}: {ERROR['message']}"
        assert events == []
        audit_content = json.dumps(
            {"question": run.question, "plan": run.plan, "error": run.error}
        )
    else:
        assert len(captured) == 0
        assert SemanticQueryRun.objects.count() == 0
        if audit_mode == "disabled":
            assert events == []
        else:
            assert len(events) == 1
            event = events[0]
            assert event == {
                "timestamp": event["timestamp"],
                "principal_id": mcp_request.user.pk,
                "resource": None,
                "intent": None,
                "status": "failed",
                "row_count": 0,
                "duration_ms": None,
                "error_code": ERROR["code"],
                "error_message": ERROR["message"],
            }
        audit_content = json.dumps(events, default=str)
    # No result/plan, partial rows, or output-policy pseudo-success.
    assert payload == expected
    for private in (
        str(PRIVATE_FILTER),
        PRIVATE_DIAGNOSTIC,
        "paid",
        "pending",
        "customer__email",
    ):
        assert private not in json.dumps(payload)
        assert private not in audit_content
    assert QUESTION not in audit_content


@pytest.mark.parametrize("budget", ["MAX_ROWS", "MAX_FILTERS"])
@pytest.mark.parametrize("allow_rows,include_rows,row_cap", ROW_POLICIES)
def test_mcp_at_budget_still_executes_and_audits_with_empty_data(
    budget: str,
    allow_rows: bool,
    include_rows: bool | None,
    row_cap: int,
    settings,
    registered_orders,
    order_data,
    mcp_request,
) -> None:
    """An empty MCP data array neither means no execution nor zero query cost."""

    settings.DJANGO_ASKLENS.update(
        {
            budget: 2,
            "AUDIT_MODE": "database",
            "AUDIT_INCLUDE_CONTENT": False,
            "MCP_ALLOW_ROW_RETURN": allow_rows,
            "MCP_MAX_RETURNED_ROWS": row_cap,
        }
    )
    with CaptureQueriesContext(connection) as captured:
        payload = asklens_execute_plan(
            mcp_request, budget_plan(), question=QUESTION, **row_arguments(include_rows)
        )

    assert len(captured) == 2
    select, audit_insert = [query["sql"].strip().upper() for query in captured]
    assert select.startswith("SELECT") and "TEST_PROJECT_ORDER" in select
    assert audit_insert.startswith('INSERT INTO "ASKLENS_SEMANTICQUERYRUN"')
    assert payload["response_type"] == "query"
    assert payload["row_count"] == 2
    assert payload["data"] == []
    assert payload["result_metadata"] == {
        "limit": 2,
        "limit_scope": "groups",
        "truncated": False,
    }
    if allow_rows and include_rows:
        assert "row_return_denied" not in payload
        assert payload["rows_omitted"] is False
        assert payload["mcp_row_limit"] == 0
        assert payload["mcp_returned_row_count"] == 0
        assert payload["mcp_rows_truncated"] is True
    else:
        assert payload["rows_omitted"] is True
        if include_rows:
            assert payload["row_return_denied"] is True
        else:
            assert "row_return_denied" not in payload
    run = SemanticQueryRun.objects.get()
    assert payload["run_id"] == run.pk
    assert run.user == mcp_request.user
    assert run.question == ""
    assert run.plan == {"resource": "orders", "intent": "aggregate"}
    assert run.status == "success" and run.row_count == 2
    assert run.error == ""
