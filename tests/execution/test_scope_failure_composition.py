"""Scope-provider failures stay opaque across every executing adapter."""

import json
from collections.abc import Iterator
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from django_asklens.admin_querying import execute_admin_query
from django_asklens.catalog.registry import default_registry
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import execute_plan
from django_asklens.mcp import asklens_execute_plan
from django_asklens.models import SemanticQueryRun
from tests.execution.test_facade import build_registry, create_order, status_plan

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.postgresql]

QUESTION = "Show synthetic scope-failure orders"
PRIVATE_DIAGNOSTIC = "private-scope-diagnostic-149"
PRIVATE_ROW = "private-scope-row-149@example.test"
ERROR = {
    "code": "asklens.scope.unavailable",
    "message": "A safe query scope is unavailable for this request.",
}


@pytest.fixture(autouse=True)
def isolated_registry() -> Iterator[None]:
    default_registry.clear()
    yield
    default_registry.clear()


def invoke_adapter(adapter: str, request, plan: dict) -> tuple[dict, int | None]:
    """Invoke one real public surface and return its safe payload and audit ID."""

    if adapter == "core":
        with pytest.raises(PublicAskLensError) as caught:
            execute_plan(plan, request=request)
        payload = {"error": public_error_payload(caught.value)}
        run = caught.value._audit_record
        return payload, run.pk if run is not None else None

    if adapter == "api":
        client = APIClient()
        client.force_authenticate(user=request.user)
        response = client.post(
            "/asklens/query/",
            {"question": QUESTION, "plan": plan},
            format="json",
        )
        assert response.status_code == 400
        payload = response.json()
        assert set(payload) == {"error", "run_id"}
        return payload, payload["run_id"]

    if adapter == "admin":
        result, run, message, reused = execute_admin_query(request, question=QUESTION)
        assert result is None and reused is False
        assert message == ERROR["message"]
        assert run is not None
        return {"error": ERROR, "run_id": run.pk}, run.pk

    assert adapter == "mcp"
    payload = asklens_execute_plan(
        request,
        plan,
        question=QUESTION,
        include_rows=True,
    )
    assert payload["response_type"] == "error"
    assert payload["status_code"] == 400
    return payload, payload["run_id"]


@pytest.mark.parametrize("adapter", ["core", "api", "admin", "mcp"])
@pytest.mark.parametrize("failure", ["raises", "invalid-return"])
def test_scope_failures_never_execute_application_data_across_adapters(
    adapter: str,
    failure: str,
    settings,
) -> None:
    """Exceptions and invalid results have one safe, audited adapter outcome."""

    user = get_user_model().objects.create_user(
        username=f"scope-149-{adapter}-{failure}"
    )
    request = SimpleNamespace(user=user)
    create_order(email=PRIVATE_ROW, status="paid", total="10.00")
    scope_calls = []
    observations = []

    def scope_provider(current_request):
        scope_calls.append(current_request)
        if failure == "raises":
            raise RuntimeError(PRIVATE_DIAGNOSTIC)
        return None

    resource = build_registry().get("orders")
    default_registry.register(
        model=resource.model,
        name=resource.name,
        timezone=resource.timezone,
        fields=resource.fields,
        metrics=tuple(resource.metrics.values()),
        requires_permission=resource.requires_permission,
        scope_mode="context_scoped",
        scope_provider=scope_provider,
    )
    plan = status_plan().model_dump(mode="json")
    settings.DJANGO_ASKLENS = {
        "REQUEST_PERMISSIONS_GETTER": lambda _request: {"shop.view_orders"},
        "AUDIT_MODE": "database",
        "AUDIT_INCLUDE_CONTENT": False,
        "OBSERVABILITY_SINK": observations.append,
        "LLM_BACKEND": "dummy",
        "DUMMY_PLANS": {QUESTION: {"query_plan": plan}},
        "MCP_ALLOW_ROW_RETURN": True,
    }

    with CaptureQueriesContext(connection) as captured:
        payload, run_id = invoke_adapter(adapter, request, plan)

    assert payload["error"] == ERROR
    for key in ("result", "data", "columns", "plan", "presentation"):
        assert key not in payload
    public_content = json.dumps(payload)
    assert PRIVATE_DIAGNOSTIC not in public_content
    assert PRIVATE_ROW not in public_content

    assert scope_calls == [request] or (
        adapter == "api" and len(scope_calls) == 1 and scope_calls[0].user is user
    )
    sql = [query["sql"].strip().upper() for query in captured]
    assert len(sql) == 1
    assert sql[0].startswith('INSERT INTO "ASKLENS_SEMANTICQUERYRUN"')
    assert "TEST_PROJECT_ORDER" not in sql[0]

    run = SemanticQueryRun.objects.get()
    assert run.pk == run_id
    assert run.user == user
    assert run.question == "" and run.plan == {"resource": "orders", "intent": "list"}
    assert run.status == "failed" and run.row_count == 0
    assert run.duration_ms is None
    assert run.error == f"{ERROR['code']}: {ERROR['message']}"
    assert PRIVATE_DIAGNOSTIC not in run.error
    assert PRIVATE_ROW not in json.dumps(
        {"question": run.question, "plan": run.plan, "error": run.error}
    )

    assert [event.name for event in observations] == [
        "asklens.plan.accepted",
        "asklens.execution.failed",
    ]
    assert observations[-1].error_code == ERROR["code"]
    observed_content = json.dumps([asdict(event) for event in observations])
    assert PRIVATE_DIAGNOSTIC not in observed_content
    assert PRIVATE_ROW not in observed_content
