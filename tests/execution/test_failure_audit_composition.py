"""Binding and post-read serialization failures remain opaque and audited once."""

import json
import traceback
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from django_asklens.admin_querying import execute_admin_query
from django_asklens.catalog.registry import default_registry
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import execute_plan, runner
from django_asklens.mcp import asklens_execute_plan
from django_asklens.models import SemanticQueryRun
from tests.execution.test_facade import create_order
from tests.test_project.models import Order

pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]

QUESTION = "Show orders for synthetic-failure-request-82"
PRIVATE_BINDING = "private_binding_diagnostic_82"
PRIVATE_FILTER = "private-filter-value-82"
PRIVATE_ROW = "private-state-82"
PRIVATE_EMAIL = "private-row-82@example.test"
ERRORS = {
    "binding": {
        "code": "asklens.binding.invalid",
        "message": "The query plan could not be bound safely.",
    },
    "serialization": {
        "code": "asklens.execute.failed",
        "message": "The query could not be executed.",
    },
}


@pytest.fixture(autouse=True)
def isolated_registry() -> Iterator[None]:
    default_registry.clear()
    yield
    default_registry.clear()


def build_case(settings, mode: str, *, invalid_row: bool = True):
    """Seed a valid row before the invalid row so partial results are detectable."""

    user = get_user_model().objects.create_user(username="failure-82", is_staff=True)
    request = SimpleNamespace(user=user)
    create_order(email=PRIVATE_EMAIL, status="paid", total="10.00")
    create_order(
        email=PRIVATE_EMAIL,
        status=PRIVATE_ROW if invalid_row else "paid",
        total="20.00",
    )
    default_registry.register(
        name="orders",
        model=Order,
        timezone="UTC",
        scope_mode="global",
        fields={
            "state": {
                "binding": "status",
                "type": "enum",
                "nullable": False,
                "enum": {"type": "string", "values": [{"value": "paid"}]},
            },
            "note": {"binding": "internal_notes", "type": "string", "nullable": False},
        },
    )
    plan = {
        "resource": "orders",
        "intent": "list",
        "select": ["state"],
        "filters": [{"field": "note", "op": "neq", "value": PRIVATE_FILTER}],
        "limit": 10,
    }
    events = []

    def sink(event):
        events.append(event)
        if mode == "failing-custom":
            raise RuntimeError(PRIVATE_BINDING)

    settings.DJANGO_ASKLENS = {
        "REQUEST_PERMISSIONS_GETTER": lambda _request: (),
        "AUDIT_MODE": "custom" if mode == "failing-custom" else mode,
        "AUDIT_SINK": sink,
        "AUDIT_INCLUDE_CONTENT": False,
        "LLM_BACKEND": "dummy",
        "DUMMY_PLANS": {QUESTION: {"query_plan": plan}},
        "MCP_ALLOW_ROW_RETURN": True,
    }
    return request, plan, events


def invoke_failure(adapter: str, request, plan, expected_error: dict):
    """Check real public surfaces; return their audit ID, without inventing codes."""

    if adapter == "core":
        with pytest.raises(PublicAskLensError) as caught:
            execute_plan(plan, request=request)
        assert public_error_payload(caught.value) == expected_error
        assert str(caught.value) == expected_error["message"]
        formatted = "".join(traceback.format_exception(caught.value))
        for private in (PRIVATE_BINDING, PRIVATE_FILTER, PRIVATE_ROW, PRIVATE_EMAIL):
            assert private not in formatted
        run = caught.value._audit_record
        return run.pk if run is not None else None

    if adapter == "api":
        client = APIClient()
        client.force_authenticate(user=request.user)
        response = client.post(
            "/asklens/query/", {"question": QUESTION, "plan": plan}, format="json"
        )
        assert response.status_code == 400
        payload = response.json()
        assert set(payload) in ({"error"}, {"error", "run_id"})
    elif adapter == "admin":
        result, run, message, reused = execute_admin_query(request, question=QUESTION)
        assert result is None and reused is False
        assert message == expected_error["message"]
        return run.pk if run is not None else None
    else:
        assert adapter == "mcp"
        payload = asklens_execute_plan(
            request, plan, question=QUESTION, include_rows=True
        )
        assert payload["response_type"] == "error"
        assert payload["status_code"] == 400

    assert payload["error"] == expected_error
    for key in ("result", "data", "columns", "plan", "presentation"):
        assert key not in payload
    public_content = json.dumps(payload)
    for private in (
        PRIVATE_BINDING,
        PRIVATE_FILTER,
        PRIVATE_ROW,
        PRIVATE_EMAIL,
        "paid",
    ):
        assert private not in public_content
    return payload.get("run_id")


@pytest.mark.parametrize("adapter", ["core", "api", "admin", "mcp"])
@pytest.mark.parametrize("mode", ["disabled", "database", "custom", "failing-custom"])
@pytest.mark.parametrize(
    "binding_error",
    [FieldError, KeyError, None],
    ids=["field-error", "key-error", "serialization"],
)
def test_failure_stages_preserve_opacity_and_exact_audit_effects(
    adapter: str, mode: str, binding_error, settings, monkeypatch
) -> None:
    request, plan, events = build_case(settings, mode)
    expected_error = ERRORS["binding" if binding_error is not None else "serialization"]
    compiler = (
        Mock(side_effect=binding_error(PRIVATE_BINDING))
        if binding_error is not None
        else Mock(wraps=runner._compile_prepared_query)
    )
    audit = Mock(wraps=runner._audit_execution)
    monkeypatch.setattr(
        "django_asklens.execution.runner._compile_prepared_query", compiler
    )
    monkeypatch.setattr("django_asklens.execution.runner._audit_execution", audit)

    with CaptureQueriesContext(connection) as captured:
        run_id = invoke_failure(adapter, request, plan, expected_error)

    compiler.assert_called_once()
    audit.assert_called_once()
    assert audit.call_args.kwargs["result"] is None
    assert public_error_payload(audit.call_args.kwargs["error"]) == expected_error
    assert audit.call_args.kwargs["validated_plan"].resource == "orders"

    sql = [query["sql"].strip().upper() for query in captured]
    expected_reads = 0 if binding_error is not None else 1
    assert len(sql) == expected_reads + (mode == "database")
    if expected_reads:
        assert sql[0].startswith("SELECT") and "TEST_PROJECT_ORDER" in sql[0]
    if mode == "database":
        assert sql[-1].startswith('INSERT INTO "ASKLENS_SEMANTICQUERYRUN"')
        assert events == []
        run = SemanticQueryRun.objects.get()
        assert run.pk == run_id
        assert run.user == request.user
        assert run.question == ""
        assert run.plan == {"resource": "orders", "intent": "list"}
        assert run.status == "failed"
        assert run.row_count == 0 and run.duration_ms is None
        assert run.error == f"{expected_error['code']}: {expected_error['message']}"
        audit_content = json.dumps(
            {"question": run.question, "plan": run.plan, "error": run.error}
        )
    else:
        assert run_id is None
        assert SemanticQueryRun.objects.count() == 0
        if mode == "disabled":
            assert events == []
        else:
            assert len(events) == 1
            event = events[0]
            assert event == {
                "timestamp": event["timestamp"],
                "principal_id": request.user.pk,
                "resource": "orders",
                "intent": "list",
                "status": "failed",
                "row_count": 0,
                "duration_ms": None,
                "error_code": expected_error["code"],
                "error_message": expected_error["message"],
            }
        audit_content = json.dumps(events, default=str)
    for private in (
        QUESTION,
        PRIVATE_BINDING,
        PRIVATE_FILTER,
        PRIVATE_ROW,
        PRIVATE_EMAIL,
    ):
        assert private not in audit_content


def test_valid_stored_rows_are_reachable_through_the_same_fixture(
    settings, django_assert_num_queries
) -> None:
    """The negative serialization fixture is neither an empty nor rejected query."""

    request, plan, events = build_case(settings, "disabled", invalid_row=False)
    with django_assert_num_queries(1):
        result = execute_plan(plan, request=request)
    assert result.to_dict()["data"] == [{"state": "paid"}, {"state": "paid"}]
    assert result.row_count == 2
    assert events == []
