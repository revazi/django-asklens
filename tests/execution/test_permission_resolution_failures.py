"""Permission resolution fails closed before planning, help, or data execution."""

import json
import traceback
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from django_asklens.admin_querying import execute_admin_query
from django_asklens.catalog.registry import default_registry
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import execute_plan
from django_asklens.mcp import asklens_query
from django_asklens.models import SemanticQueryRun
from django_asklens.querying import execute_asklens_query_request
from tests.execution.test_facade import build_registry, request_with, status_plan

pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]

PRIVATE_DIAGNOSTIC = "private-permission-diagnostic-82"
ERROR = {
    "code": "asklens.authorization.denied",
    "message": "The current request is not authorized to execute this query.",
}
AUDIT_MODES = ["disabled", "database", "custom", "failing-custom"]


def failing_permissions(_request):
    raise RuntimeError(PRIVATE_DIAGNOSTIC)


@pytest.fixture(autouse=True)
def prevent_execution(monkeypatch):
    """Guard preparation even when a public adapter catches a trap exception."""

    default_registry.clear()
    preparation = Mock(
        side_effect=AssertionError("Permission failure reached preparation.")
    )
    monkeypatch.setattr(
        "django_asklens.execution.runner._prepare_query_plan", preparation
    )
    yield
    default_registry.clear()
    preparation.assert_not_called()


def configure_audit(settings, mode: str, events: list) -> None:
    def sink(event):
        events.append(event)
        if mode == "failing-custom":
            raise RuntimeError(PRIVATE_DIAGNOSTIC)

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "custom" if mode == "failing-custom" else mode,
        "AUDIT_SINK": sink,
        "AUDIT_INCLUDE_CONTENT": False,
        "LLM_BACKEND": "openai_compatible",
    }


def call_adapter(adapter: str, request, question: str):
    """Check the actual adapter contract and return its optional audit ID."""

    if adapter == "api":
        client = APIClient()
        client.force_authenticate(user=request.user)
        response = client.post("/asklens/query/", {"question": question}, format="json")
        assert response.status_code == 400
        payload = response.json()
        assert set(payload) in ({"error"}, {"error", "run_id"})
    elif adapter == "admin":
        result, run, message, reused = execute_admin_query(request, question=question)
        assert result is None and reused is False
        assert message == ERROR["message"]
        return run.pk if run is not None else None
    elif adapter == "mcp":
        payload = asklens_query(request, question)
        assert payload["response_type"] == "error"
        assert payload["status_code"] == 400
    else:
        assert adapter == "orchestration"
        outcome = execute_asklens_query_request(request, question=question)
        assert outcome.response_type == "error"
        assert outcome.status_code == 400
        payload = outcome.payload

    assert payload["error"] == ERROR
    assert (
        "result" not in payload and "data" not in payload and "catalog" not in payload
    )
    assert PRIVATE_DIAGNOSTIC not in json.dumps(payload)
    return payload.get("run_id")


def assert_safe_audit(mode: str, events: list, captured, run_id, user) -> None:
    """Distinguish allowed audit effects from application SQL and private content."""

    if mode == "database":
        assert len(captured) == 1
        assert (
            captured[0]["sql"]
            .strip()
            .upper()
            .startswith('INSERT INTO "ASKLENS_SEMANTICQUERYRUN"')
        )
        run = SemanticQueryRun.objects.get()
        assert run.pk == run_id
        assert run.user == user
        assert run.question == "" and run.plan == {}
        assert run.status == "failed" and run.row_count == 0
        assert run.duration_ms is None
        assert run.error == f"{ERROR['code']}: {ERROR['message']}"
        assert events == []
    else:
        assert len(captured) == 0
        assert run_id is None
        assert SemanticQueryRun.objects.count() == 0
        if mode == "disabled":
            assert events == []
        else:
            assert len(events) == 1
            event = events[0]
            assert event == {
                "timestamp": event["timestamp"],
                "principal_id": user.pk,
                "resource": None,
                "intent": None,
                "status": "failed",
                "row_count": 0,
                "duration_ms": None,
                "error_code": ERROR["code"],
                "error_message": ERROR["message"],
            }
            assert PRIVATE_DIAGNOSTIC not in json.dumps(event, default=str)


@pytest.mark.parametrize("adapter", ["orchestration", "admin", "mcp", "api"])
@pytest.mark.parametrize("mode", AUDIT_MODES)
@pytest.mark.parametrize("question", ["Show orders", "What can I ask?"])
def test_initial_permission_failure_never_plans_or_falls_back_to_help(
    adapter: str, mode: str, question: str, settings, monkeypatch
) -> None:
    user = get_user_model().objects.create_user(username="permission-82", is_staff=True)
    request = SimpleNamespace(user=user)
    events = []
    configure_audit(settings, mode, events)
    resolver = Mock(side_effect=failing_permissions)
    settings.DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"] = resolver
    traps = []
    for name in (
        "plan_question",
        "plan_asklens_response",
        "route_question_intent",
        "build_query_guidance",
        "_build_capabilities_payload",
        "execute_plan",
    ):
        trap = Mock(
            side_effect=AssertionError(
                "Permission failure reached planning/help/facade."
            )
        )
        monkeypatch.setattr(f"django_asklens.querying.{name}", trap)
        traps.append(trap)

    with CaptureQueriesContext(connection) as captured:
        run_id = call_adapter(adapter, request, question)

    resolver.assert_called_once()
    for trap in traps:
        trap.assert_not_called()
    assert_safe_audit(mode, events, captured, run_id, user)


@pytest.mark.parametrize("surface", ["facade", "orchestration"])
@pytest.mark.parametrize(
    "getter",
    [
        failing_permissions,
        lambda _request: "shop.view_orders",
        lambda _request: 42,
        "private_permission_backend_82.missing_getter",
        42,
    ],
    ids=["raises", "string-result", "non-iterable", "missing-import", "not-callable"],
)
def test_permission_configuration_failures_use_existing_safe_code(
    surface: str, getter, settings, django_assert_num_queries
) -> None:
    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "REQUEST_PERMISSIONS_GETTER": getter,
    }
    with django_assert_num_queries(0):
        if surface == "facade":
            with pytest.raises(PublicAskLensError) as caught:
                execute_plan(
                    status_plan(), request=request_with(), registry=build_registry()
                )
            error = public_error_payload(caught.value)
            formatted = "".join(traceback.format_exception(caught.value))
            assert PRIVATE_DIAGNOSTIC not in formatted
            assert "private_permission_backend_82" not in formatted
        else:
            outcome = execute_asklens_query_request(
                request_with(),
                question="Show orders",
                provided_plan=status_plan().model_dump(mode="json"),
            )
            assert outcome.status_code == 400 and outcome.run is None
            error = outcome.payload["error"]
    assert error == ERROR


@pytest.mark.parametrize("mode", AUDIT_MODES)
def test_facade_permission_refresh_failure_cannot_use_earlier_help_permissions(
    mode: str, settings, monkeypatch
) -> None:
    """Even after planning, a failed fresh resolver cannot authorize help fallback."""

    user = get_user_model().objects.create_user(username="refresh-82", is_staff=True)
    request = SimpleNamespace(user=user)
    events = []
    configure_audit(settings, mode, events)
    resolver = Mock(
        side_effect=[frozenset({"shop.view_orders"}), RuntimeError(PRIVATE_DIAGNOSTIC)]
    )
    settings.DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"] = resolver
    resource = build_registry().get("orders")
    default_registry.register(
        name=resource.name,
        model=resource.model,
        fields=resource.fields,
        metrics=tuple(resource.metrics.values()),
        timezone="UTC",
        requires_permission="shop.view_orders",
        scope_mode="context_scoped",
        scope_provider=resource.scope_provider,
    )
    provider = SimpleNamespace(
        complete_json=Mock(
            return_value={
                "response_type": "query",
                "query_plan": status_plan().model_dump(mode="json"),
            }
        )
    )
    monkeypatch.setattr(
        "django_asklens.planning.responses.get_llm_provider", lambda: provider
    )
    help_payload = Mock(
        side_effect=AssertionError("Failed fresh permissions reached help fallback.")
    )
    monkeypatch.setattr(
        "django_asklens.querying._build_capabilities_payload", help_payload
    )

    with CaptureQueriesContext(connection) as captured:
        run_id = call_adapter("orchestration", request, "What can I ask?")

    assert resolver.call_count == 2
    provider.complete_json.assert_called_once()
    help_payload.assert_not_called()
    assert_safe_audit(mode, events, captured, run_id, user)
