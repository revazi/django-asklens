"""Provider-time permission changes must survive every executing adapter."""

import json
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from django_asklens.admin_querying import execute_admin_query
from django_asklens.catalog.registry import default_registry
from django_asklens.execution import execute_plan
from django_asklens.execution.runner import _compile_prepared_query
from django_asklens.mcp import asklens_query
from django_asklens.models import SemanticQueryRun
from django_asklens.planning import parse_query_plan
from tests.execution.test_facade import build_registry, create_order
from tests.test_project.models import Order

pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]

QUESTION = "Show customer contacts for synthetic-request-82"
PRIVATE_EMAIL = "private-row-82@example.test"
PRIVATE_FILTER = "private-filter-82"
INITIAL_PERMISSIONS = frozenset({"shop.view_orders", "shop.view_customer_pii"})
MEMBER_ERROR = {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable.",
}


@pytest.fixture(autouse=True)
def isolated_registry() -> Iterator[None]:
    """Leave shared adapter registrations clean even after an assertion fails."""

    default_registry.clear()
    yield
    default_registry.clear()


def invoke_adapter(adapter: str, user, *, revoked: bool) -> dict:
    """Use each real adapter and check its existing success/error envelope."""

    if adapter == "api":
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post("/asklens/query/", {"question": QUESTION}, format="json")
        assert response.status_code == (400 if revoked else 200)
        payload = response.json()
        if revoked:
            assert set(payload) == {"error", "run_id"}
            assert payload["error"] == MEMBER_ERROR
        return payload

    request = RequestFactory().post("/admin/asklens/asklensquery/")
    request.user = user
    if adapter == "admin":
        result, run, error, reused = execute_admin_query(request, question=QUESTION)
        assert run is not None
        assert reused is False
        if revoked:
            assert result is None
            assert error == MEMBER_ERROR["message"]
            return {"error": error, "run_id": run.pk}
        assert error == ""
        assert result is not None
        return result

    assert adapter == "mcp"
    payload = asklens_query(request, QUESTION, include_rows=True)
    if revoked:
        assert payload["response_type"] == "error"
        assert payload["status_code"] == 400
        assert payload["error"] == MEMBER_ERROR
        assert "data" not in payload
    else:
        assert payload["rows_omitted"] is False
    return payload


@pytest.mark.parametrize("adapter", ["api", "admin", "mcp"])
@pytest.mark.parametrize("planner", ["dummy", "unified"])
@pytest.mark.parametrize("revoked", [True, False], ids=["revoked", "retained"])
def test_adapters_recheck_permissions_after_provider_planning(
    adapter: str,
    planner: str,
    revoked: bool,
    settings,
    monkeypatch,
) -> None:
    """A plan validated with old permissions cannot authorize current execution."""

    user = get_user_model().objects.create_user(username="adapter-82", is_staff=True)
    create_order(email=PRIVATE_EMAIL, status="paid", total="10.00")
    current_permissions = INITIAL_PERMISSIONS
    permission_reads = []
    scope_calls = []
    provider_calls = []

    def permissions_for(request):
        permission_reads.append((request, current_permissions))
        return current_permissions

    def scoped_orders(request):
        scope_calls.append(request)
        return Order.objects.filter(status="paid")

    resource = build_registry().get("orders")
    default_registry.register(
        name=resource.name,
        model=resource.model,
        fields=resource.fields,
        metrics=tuple(resource.metrics.values()),
        timezone="UTC",
        requires_permission="shop.view_orders",
        scope_mode="context_scoped",
        scope_provider=scoped_orders,
    )
    plan = {
        "resource": "orders",
        "intent": "list",
        "select": ["customer.email"],
        "filters": [{"field": "status", "op": "neq", "value": PRIVATE_FILTER}],
        "limit": 10,
    }

    def complete_json(*, messages, schema):
        nonlocal current_permissions
        provider_calls.append((messages, schema))
        if revoked:
            current_permissions = frozenset({"shop.view_orders"})
        payload = {"query_plan": plan}
        if planner == "unified":
            payload["response_type"] = "query"
        return payload

    settings.DJANGO_ASKLENS = {
        "REQUEST_PERMISSIONS_GETTER": permissions_for,
        "AUDIT_MODE": "database",
        "AUDIT_INCLUDE_CONTENT": False,
        "LLM_BACKEND": "dummy" if planner == "dummy" else "openai_compatible",
        "MCP_ALLOW_ROW_RETURN": True,
    }
    provider = SimpleNamespace(complete_json=complete_json)
    provider_module = "planner" if planner == "dummy" else "responses"
    monkeypatch.setattr(
        f"django_asklens.planning.{provider_module}.get_llm_provider", lambda: provider
    )
    facade = Mock(wraps=execute_plan)
    compiler = Mock(wraps=_compile_prepared_query)
    monkeypatch.setattr("django_asklens.querying.execute_plan", facade)
    monkeypatch.setattr(
        "django_asklens.execution.runner._compile_prepared_query", compiler
    )

    with CaptureQueriesContext(connection) as captured:
        payload = invoke_adapter(adapter, user, revoked=revoked)

    assert len(provider_calls) == 1
    messages, schema = provider_calls[0]
    assert schema["title"] == (
        "PlannerProviderResponse" if planner == "dummy" else "AskLensProviderResponse"
    )
    prompt = json.dumps(messages)
    assert "customer.email" in prompt  # Authorized at provider-request time.
    for private in (
        PRIVATE_EMAIL,
        PRIVATE_FILTER,
        "customer__email",
        *INITIAL_PERMISSIONS,
    ):
        assert private not in prompt

    assert len(permission_reads) == 2
    original_request, original_permissions = permission_reads[0]
    current_request, resolved_permissions = permission_reads[1]
    assert original_request is current_request
    assert current_request.user is user
    assert original_permissions == INITIAL_PERMISSIONS
    assert resolved_permissions == current_permissions
    facade.assert_called_once()
    assert facade.call_args.kwargs == {"request": current_request}
    assert facade.call_args.args == (parse_query_plan(plan),)

    sql = [query["sql"].strip().upper() for query in captured]
    audit_sql = [
        statement for statement in sql if "ASKLENS_SEMANTICQUERYRUN" in statement
    ]
    assert len(audit_sql) == 1
    assert audit_sql[0].startswith('INSERT INTO "ASKLENS_SEMANTICQUERYRUN"')
    if revoked:
        assert sql == audit_sql  # No application-data SQL, not merely zero rows.
        assert scope_calls == []
        compiler.assert_not_called()
    else:
        assert len(sql) == 2
        assert sql[0].startswith("SELECT")
        assert "TEST_PROJECT_ORDER" in sql[0]
        assert scope_calls == [current_request]
        compiler.assert_called_once()
        result = payload if adapter == "mcp" else payload["result"]
        assert result["data"] == [{"customer.email": PRIVATE_EMAIL}]
        assert result["row_count"] == 1

    run = SemanticQueryRun.objects.get()
    assert payload["run_id"] == run.pk
    assert run.user == user
    assert run.question == ""
    assert run.plan == ({} if revoked else {"resource": "orders", "intent": "list"})
    assert run.status == ("failed" if revoked else "success")
    assert run.row_count == (0 if revoked else 1)
    assert run.error == (
        f"{MEMBER_ERROR['code']}: {MEMBER_ERROR['message']}" if revoked else ""
    )
    audit_content = json.dumps(
        {"question": run.question, "plan": run.plan, "error": run.error}
    )
    for private in (
        QUESTION,
        PRIVATE_FILTER,
        PRIVATE_EMAIL,
        "customer__email",
        *INITIAL_PERMISSIONS,
    ):
        assert private not in audit_content
    if revoked:
        assert run.duration_ms is None
        public_content = json.dumps(payload)
        for private in (
            PRIVATE_FILTER,
            PRIVATE_EMAIL,
            "customer.email",
            "customer__email",
            *INITIAL_PERMISSIONS,
        ):
            assert private not in public_content
