"""Regression expectations for safe current-context configuration failures."""

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
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import execute_plan
from django_asklens.mcp import asklens_execute_plan
from django_asklens.querying import execute_asklens_query_request
from tests.execution.test_facade import build_registry, request_with, status_plan

pytestmark = pytest.mark.django_db

PRIVATE_DIAGNOSTIC = "private-context-diagnostic-82"
MISSING_SINK = "private_audit_backend_82.missing_sink"
AUTHORIZATION_ERROR = {
    "code": "asklens.authorization.denied",
    "message": "The current request is not authorized to execute this query.",
}
BINDING_ERROR = {
    "code": "asklens.binding.invalid",
    "message": "The query plan could not be bound safely.",
}
PARSE_ERROR = {
    "code": "asklens.parse.invalid",
    "message": "The query plan could not be parsed.",
    "pointer": "/presentation",
}


def failing_permissions(_request):
    """Represent a trusted host resolver failing with private diagnostic detail."""

    raise RuntimeError(PRIVATE_DIAGNOSTIC)


@pytest.fixture(autouse=True)
def no_execution_or_provider_calls(monkeypatch):
    """Reject accidental preparation/planning even if a trap error gets caught."""

    traps = []
    for path in (
        "django_asklens.execution.runner._prepare_query_plan",
        "django_asklens.querying.plan_question",
        "django_asklens.querying.plan_asklens_response",
    ):
        trap = Mock(side_effect=AssertionError("Context failure must stop here."))
        monkeypatch.setattr(path, trap)
        traps.append(trap)
    with CaptureQueriesContext(connection) as captured:
        yield
    # User setup belongs outside SQL assertions in the adapter test below.
    for query in captured:
        sql = query["sql"].upper()
        assert "TEST_PROJECT_ORDER" not in sql
        assert "ASKLENS_SEMANTICQUERYRUN" not in sql
    for trap in traps:
        trap.assert_not_called()


@pytest.mark.parametrize(
    "getter",
    [
        failing_permissions,
        lambda _request: "shop.view_orders",
        lambda _request: 42,
        "private_permission_backend_82.missing_getter",
        42,
    ],
    ids=[
        "raises",
        "string-result",
        "non-iterable-result",
        "missing-import",
        "not-callable",
    ],
)
def test_facade_permission_configuration_errors_are_safe_before_sql(
    getter, settings, django_assert_num_queries
) -> None:
    """The existing facade wrapper must keep resolver detail private."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "REQUEST_PERMISSIONS_GETTER": getter,
    }
    with django_assert_num_queries(0), pytest.raises(PublicAskLensError) as caught:
        execute_plan(status_plan(), request=request_with(), registry=build_registry())

    assert public_error_payload(caught.value) == AUTHORIZATION_ERROR
    assert str(caught.value) == AUTHORIZATION_ERROR["message"]
    formatted = "".join(traceback.format_exception(caught.value))
    for private in (PRIVATE_DIAGNOSTIC, "private_permission_backend_82"):
        assert private not in formatted


@pytest.mark.parametrize(
    "configuration",
    [
        {"AUDIT_MODE": PRIVATE_DIAGNOSTIC},
        {"AUDIT_MODE": [PRIVATE_DIAGNOSTIC]},
        {"AUDIT_INCLUDE_CONTENT": PRIVATE_DIAGNOSTIC},
        {"AUDIT_MODE": "custom", "AUDIT_SINK": 42},
        {"AUDIT_MODE": "custom", "AUDIT_SINK": MISSING_SINK},
    ],
    ids=[
        "unknown-mode",
        "unhashable-mode",
        "non-boolean-content",
        "not-callable-sink",
        "missing-sink-import",
    ],
)
def test_facade_audit_configuration_errors_are_safe_before_sql(
    configuration, settings, django_assert_num_queries
) -> None:
    """Invalid audit configuration must not escape the public error boundary."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled", **configuration}
    with django_assert_num_queries(0), pytest.raises(PublicAskLensError) as caught:
        execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert public_error_payload(caught.value) == BINDING_ERROR
    assert str(caught.value) == BINDING_ERROR["message"]
    assert MISSING_SINK not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("adapter", ["orchestration", "admin", "mcp", "api"])
def test_initial_permission_resolver_failure_is_opaque_in_adapters(
    adapter: str, settings, django_assert_num_queries
) -> None:
    """Adapter preflight must not bypass the facade's safe resolver error policy."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "REQUEST_PERMISSIONS_GETTER": failing_permissions,
    }
    user = get_user_model().objects.create_user(
        username="context-failure-82", is_staff=True
    )
    request = SimpleNamespace(user=user)
    plan = status_plan().model_dump(mode="json")
    question = "Show orders"

    with django_assert_num_queries(0):
        if adapter == "orchestration":
            outcome = execute_asklens_query_request(
                request, question=question, provided_plan=plan
            )
            assert outcome.status_code == 400
            error = outcome.payload["error"]
        elif adapter == "admin":
            result, run, message, reused = execute_admin_query(
                request, question=question
            )
            assert result is None and run is None and reused is False
            assert message == AUTHORIZATION_ERROR["message"]
            return
        elif adapter == "mcp":
            payload = asklens_execute_plan(request, plan)
            assert payload["response_type"] == "error"
            error = payload["error"]
        else:
            client = APIClient()
            client.force_authenticate(user=user)
            response = client.post(
                "/asklens/query/", {"question": question, "plan": plan}, format="json"
            )
            assert response.status_code == 400
            error = response.json()["error"]

    assert error == AUTHORIZATION_ERROR
    assert PRIVATE_DIAGNOSTIC not in json.dumps(error)


def test_audit_sink_import_failure_does_not_replace_original_parse_rejection(
    settings, django_assert_num_queries
) -> None:
    """External rejection auditing cannot replace a safe error with import detail."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "custom",
        "AUDIT_SINK": MISSING_SINK,
    }
    with django_assert_num_queries(0):
        outcome = execute_asklens_query_request(
            request_with(),
            question="Show orders",
            provided_plan={},
            provided_presentation={"kind": PRIVATE_DIAGNOSTIC},
        )

    assert outcome.status_code == 400
    assert outcome.run is None
    assert outcome.payload["error"] == PARSE_ERROR
    assert MISSING_SINK not in json.dumps(outcome.payload)
