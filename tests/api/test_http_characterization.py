"""Characterize the current alpha DRF transport without changing its contract."""

import json
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from django_asklens import Metric
from django_asklens.api.views import (
    CapabilitiesView,
    CatalogView,
    QueryRunDetailView,
    QueryView,
)
from django_asklens.catalog.registry import default_registry
from django_asklens.models import SemanticQueryRun
from tests.test_project.models import Order

pytestmark = pytest.mark.django_db

QUESTION = "Count synthetic orders"
PRIVATE_FIELD = "private_note"
PRIVATE_BINDING = "internal_notes"
PRIVATE_PERMISSION = "test_project.view_private_note"
MISSING_FIELD = "never_registered"
APPLICATION_TABLE = "test_project_order"
AUDIT_TABLE = "asklens_semanticqueryrun"
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE")
ROUTES = (
    ("catalog", "/asklens/catalog/", CatalogView, "get"),
    ("capabilities", "/asklens/capabilities/", CapabilitiesView, "get"),
    ("query", "/asklens/query/", QueryView, "post"),
    ("run-detail", "/asklens/runs/{pk}/", QueryRunDetailView, "get"),
)


@pytest.fixture(autouse=True)
def isolate_registry() -> None:
    """Keep the characterization catalog isolated from other tests."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Return a DRF client for transport-boundary assertions."""

    return APIClient()


@pytest.fixture
def user():
    """Return a current authenticated non-staff principal."""

    return get_user_model().objects.create_user(username="api-characterization-user")


@pytest.fixture
def staff_user():
    """Return a current authenticated staff principal."""

    return get_user_model().objects.create_user(
        username="api-characterization-staff",
        is_staff=True,
    )


@pytest.fixture
def registered_orders() -> None:
    """Register one synthetic resource with one permission-gated field."""

    default_registry.register(
        model=Order,
        name="orders",
        label="Orders",
        timezone="UTC",
        scope_mode="global",
        fields={
            "id": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
            },
            "status": {
                "binding": "status",
                "type": "string",
                "nullable": False,
            },
            PRIVATE_FIELD: {
                "binding": PRIVATE_BINDING,
                "type": "string",
                "nullable": False,
                "requires_permission": PRIVATE_PERMISSION,
            },
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
    )


def aggregate_plan() -> dict[str, Any]:
    """Return one deterministic plan supplied directly by the test client."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "metrics": [{"metric": "order_count"}],
        "limit": 10,
    }


def list_plan(field: str) -> dict[str, Any]:
    """Return one list plan selecting a possibly unavailable member."""

    return {
        "resource": "orders",
        "intent": "list",
        "select": [field],
        "limit": 10,
    }


def route_path(template: str, *, pk: int) -> str:
    """Resolve the run-detail placeholder used by parameterized route tests."""

    return template.format(pk=pk)


def request_route(client: APIClient, method: str, path: str):
    """Issue one route request with a valid body when POST is supported."""

    if method == "POST" and path == "/asklens/query/":
        return client.post(
            path,
            {"question": QUESTION, "plan": aggregate_plan()},
            format="json",
        )
    return client.generic(method, path)


def assert_json_response(response) -> None:
    """Assert the current renderer's exact JSON media type."""

    assert response.content is not None
    assert response["Content-Type"] == "application/json"


def application_sql(queries: list[dict[str, str]]) -> list[str]:
    """Return statements targeting the registered application-data table."""

    return [
        query["sql"] for query in queries if APPLICATION_TABLE in query["sql"].lower()
    ]


@pytest.mark.parametrize(
    ("route_name", "path_template", "_view_class", "_handler"),
    ROUTES,
    ids=[case[0] for case in ROUTES],
)
def test_routes_characterize_exact_http_methods_and_allow_headers(
    route_name: str,
    path_template: str,
    _view_class,
    _handler: str,
    api_client: APIClient,
    user,
    registered_orders: None,
) -> None:
    """All standard DRF methods are either handled or return stable JSON 405s."""

    run = SemanticQueryRun.objects.create(
        user=user,
        question="",
        plan={"resource": "orders", "intent": "aggregate"},
        status=SemanticQueryRun.Status.SUCCESS,
    )
    path = route_path(path_template, pk=run.pk)
    api_client.force_authenticate(user=user)
    expected_allow = "POST, OPTIONS" if route_name == "query" else "GET, HEAD, OPTIONS"
    allowed = (
        {"POST", "OPTIONS"}
        if route_name == "query"
        else {
            "GET",
            "HEAD",
            "OPTIONS",
        }
    )

    for method in HTTP_METHODS:
        response = request_route(api_client, method, path)

        assert_json_response(response)
        assert response["Allow"] == expected_allow
        if method in allowed:
            assert response.status_code == 200
        else:
            assert response.status_code == 405
            if method == "HEAD":
                assert response.content == b""
            else:
                assert response.json() == {"detail": f'Method "{method}" not allowed.'}


def test_route_successes_have_current_json_status_and_top_level_shapes(
    api_client: APIClient,
    user,
    registered_orders: None,
) -> None:
    """Pin transport wrappers only, leaving nested document identity to API-2."""

    api_client.force_authenticate(user=user)

    catalog = api_client.get("/asklens/catalog/")
    capabilities = api_client.get("/asklens/capabilities/")
    query = api_client.post(
        "/asklens/query/",
        {
            "question": QUESTION,
            "plan": aggregate_plan(),
            "presentation": {"kind": "table"},
        },
        format="json",
    )
    run_detail = api_client.get(f"/asklens/runs/{query.data['run_id']}/")

    for response in (catalog, capabilities, query, run_detail):
        assert response.status_code == 200
        assert_json_response(response)
    assert set(catalog.data) == {"resources"}
    assert set(capabilities.data) == {
        "intents",
        "filter_logic",
        "types",
        "time_grains",
        "limits",
        "features",
        "aggregate_policies",
        "backend_restrictions",
    }
    assert set(query.data) == {
        "question",
        "response_type",
        "plan",
        "columns",
        "data",
        "row_count",
        "duration_ms",
        "result_metadata",
        "explanation",
        "run_id",
        "presentation",
    }
    assert query.data["response_type"] == "query"
    assert set(run_detail.data) == {
        "id",
        "question",
        "plan",
        "status",
        "row_count",
        "duration_ms",
        "error",
        "created_at",
    }


@pytest.mark.parametrize(
    ("_route_name", "path_template", "view_class", "handler"),
    ROUTES,
    ids=[case[0] for case in ROUTES],
)
def test_default_anonymous_denial_is_exact_and_precedes_route_handlers_and_sql(
    _route_name: str,
    path_template: str,
    view_class,
    handler: str,
    api_client: APIClient,
    monkeypatch,
) -> None:
    """Default anonymous denial is a framework 403 before handler or SQL work."""

    def fail_handler(*args, **kwargs):
        raise AssertionError("Anonymous denial must precede the route handler.")

    monkeypatch.setattr(view_class, handler, fail_handler)
    path = route_path(path_template, pk=999_999)

    with CaptureQueriesContext(connection) as captured:
        response = request_route(
            api_client,
            "POST" if handler == "post" else "GET",
            path,
        )

    assert response.status_code == 403
    assert_json_response(response)
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }
    assert captured.captured_queries == []
    assert SemanticQueryRun.objects.count() == 0


@pytest.mark.parametrize(
    ("_route_name", "path_template", "view_class", "handler"),
    ROUTES,
    ids=[case[0] for case in ROUTES],
)
def test_configured_route_permission_denial_precedes_handlers_audit_and_sql(
    settings,
    _route_name: str,
    path_template: str,
    view_class,
    handler: str,
    api_client: APIClient,
    user,
    monkeypatch,
) -> None:
    """A configured deny-all gate applies before all four route handlers."""

    settings.DJANGO_ASKLENS = {
        "API_PERMISSION_CLASSES": [
            "tests.test_project.permissions.DenyAskLensAccess",
        ]
    }

    def fail_handler(*args, **kwargs):
        raise AssertionError("Configured permission denial must precede the handler.")

    monkeypatch.setattr(view_class, handler, fail_handler)
    api_client.force_authenticate(user=user)
    path = route_path(path_template, pk=999_999)

    with CaptureQueriesContext(connection) as captured:
        response = request_route(
            api_client,
            "POST" if handler == "post" else "GET",
            path,
        )

    assert response.status_code == 403
    assert_json_response(response)
    assert response.json() == {
        "detail": "You do not have permission to perform this action."
    }
    assert captured.captured_queries == []
    assert SemanticQueryRun.objects.count() == 0


@pytest.mark.parametrize(
    "payload",
    ({}, {"question": ""}, {"question": " \t "}),
    ids=("missing", "empty", "whitespace"),
)
def test_query_missing_or_blank_question_uses_normalized_parse_envelope_without_audit(
    payload: dict[str, Any],
    api_client: APIClient,
    user,
    monkeypatch,
) -> None:
    """Missing and blank questions share one generic request-shape response."""

    def fail_orchestrator(*args, **kwargs):
        raise AssertionError("Invalid request shape must not reach orchestration.")

    monkeypatch.setattr(
        "django_asklens.api.views.execute_asklens_query_request",
        fail_orchestrator,
    )
    api_client.force_authenticate(user=user)

    with CaptureQueriesContext(connection) as captured:
        response = api_client.post("/asklens/query/", payload, format="json")

    assert response.status_code == 400
    assert_json_response(response)
    assert response.json() == {
        "response_type": "error",
        "error": {
            "code": "asklens.parse.invalid",
            "message": "The query request could not be parsed.",
        },
    }
    assert captured.captured_queries == []
    assert SemanticQueryRun.objects.count() == 0


@pytest.mark.parametrize(
    "case",
    ("unsupported-media", "malformed-json", "non-object-json"),
)
def test_query_transport_parse_denials_do_not_reach_orchestration_or_audit(
    case: str,
    api_client: APIClient,
    user,
    monkeypatch,
) -> None:
    """Current DRF parser and serializer denials remain unaudited."""

    def fail_orchestrator(*args, **kwargs):
        raise AssertionError("Transport parse denial must not reach orchestration.")

    monkeypatch.setattr(
        "django_asklens.api.views.execute_asklens_query_request",
        fail_orchestrator,
    )
    api_client.force_authenticate(user=user)

    with CaptureQueriesContext(connection) as captured:
        if case == "unsupported-media":
            response = api_client.generic(
                "POST",
                "/asklens/query/",
                data=b'{"question":"ignored"}',
                content_type="text/plain",
            )
        elif case == "malformed-json":
            response = api_client.generic(
                "POST",
                "/asklens/query/",
                data=b"{",
                content_type="application/json",
            )
        else:
            response = api_client.generic(
                "POST",
                "/asklens/query/",
                data=json.dumps(["not", "an", "object"]),
                content_type="application/json",
            )

    assert_json_response(response)
    if case == "unsupported-media":
        assert response.status_code == 415
        assert response.json() == {
            "detail": 'Unsupported media type "text/plain" in request.'
        }
    elif case == "malformed-json":
        assert response.status_code == 400
        assert set(response.json()) == {"detail"}
        assert response.json()["detail"].startswith("JSON parse error - ")
    else:
        assert response.status_code == 400
        assert response.json() == {
            "response_type": "error",
            "error": {
                "code": "asklens.parse.invalid",
                "message": "The query request could not be parsed.",
            },
        }
    assert captured.captured_queries == []
    assert SemanticQueryRun.objects.count() == 0


def test_query_unknown_key_is_ignored_and_optional_defaults_are_currently_permissive(
    api_client: APIClient,
    user,
    registered_orders: None,
) -> None:
    """DRF currently ignores an unknown top-level key and applies optional defaults."""

    api_client.force_authenticate(user=user)
    payload = {
        "question": QUESTION,
        "plan": aggregate_plan(),
        "presentation": {"kind": "table"},
        "unexpected": "discarded-client-value",
    }

    default_response = api_client.post("/asklens/query/", payload, format="json")
    without_presentation = api_client.post(
        "/asklens/query/",
        {**payload, "include_presentation": False},
        format="json",
    )

    assert default_response.status_code == 200
    assert default_response.data["presentation"] == {"kind": "table"}
    assert "debug" not in default_response.data
    assert "unexpected" not in default_response.data
    assert "discarded-client-value" not in str(default_response.data)
    assert without_presentation.status_code == 200
    assert "presentation" not in without_presentation.data
    assert "debug" not in without_presentation.data

    runs = list(SemanticQueryRun.objects.order_by("id"))
    assert len(runs) == 2
    for run in runs:
        assert run.user == user
        assert run.question == ""
        assert run.plan == {"resource": "orders", "intent": "aggregate"}
        assert run.status == SemanticQueryRun.Status.SUCCESS
        assert run.row_count == 1
        assert run.error == ""
        audit_text = json.dumps(run.plan)
        assert PRIVATE_BINDING not in audit_text
        assert PRIVATE_PERMISSION not in audit_text
        assert "discarded-client-value" not in audit_text


def test_hidden_and_nonexistent_members_share_opaque_error_zero_app_sql_and_safe_audit(
    api_client: APIClient,
    user,
    registered_orders: None,
) -> None:
    """Unavailable-member opacity holds at HTTP, SQL, and default-audit boundaries."""

    api_client.force_authenticate(user=user)
    assert user.get_all_permissions() == set()
    responses = []

    for field in (PRIVATE_FIELD, MISSING_FIELD):
        with CaptureQueriesContext(connection) as captured:
            response = api_client.post(
                "/asklens/query/",
                {"question": QUESTION, "plan": list_plan(field)},
                format="json",
            )
        assert application_sql(captured.captured_queries) == []
        audit_inserts = [
            query["sql"]
            for query in captured.captured_queries
            if query["sql"].lower().lstrip().startswith(f'insert into "{AUDIT_TABLE}"')
        ]
        assert len(audit_inserts) == 1
        responses.append(response)

    for response in responses:
        assert response.status_code == 400
        assert_json_response(response)
        assert set(response.data) == {"question", "status", "error", "run_id"}
        assert response.data["status"] == SemanticQueryRun.Status.FAILED
        assert response.data["error"] == {
            "code": "asklens.member.unavailable",
            "message": "A requested query member is unavailable.",
        }
        assert "response_type" not in response.data
        response_text = str(response.data)
        assert PRIVATE_FIELD not in response_text
        assert MISSING_FIELD not in response_text
        assert PRIVATE_BINDING not in response_text
        assert PRIVATE_PERMISSION not in response_text

    assert responses[0].data["error"] == responses[1].data["error"]
    runs = list(SemanticQueryRun.objects.order_by("id"))
    assert len(runs) == 2
    for run in runs:
        assert run.user == user
        assert run.question == ""
        assert run.plan == {}
        assert run.status == SemanticQueryRun.Status.FAILED
        assert run.row_count == 0
        assert run.duration_ms is None
        assert run.error == (
            "asklens.member.unavailable: A requested query member is unavailable."
        )
        audit_text = f"{run.question} {run.plan} {run.error}"
        assert PRIVATE_FIELD not in audit_text
        assert MISSING_FIELD not in audit_text
        assert PRIVATE_BINDING not in audit_text
        assert PRIVATE_PERMISSION not in audit_text


def test_nonstaff_debug_denial_precedes_trusted_execution_audit_and_sql(
    api_client: APIClient,
    user,
    registered_orders: None,
    monkeypatch,
) -> None:
    """Debug denial occurs before permission resolution, planning, or execution."""

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Non-staff debug denial must precede trusted execution.")

    monkeypatch.setattr(
        "django_asklens.querying.get_request_permissions",
        fail_if_called,
    )
    monkeypatch.setattr("django_asklens.querying.execute_plan", fail_if_called)
    api_client.force_authenticate(user=user)

    with CaptureQueriesContext(connection) as captured:
        response = api_client.post(
            "/asklens/query/",
            {"question": QUESTION, "plan": aggregate_plan(), "debug": True},
            format="json",
        )

    assert response.status_code == 403
    assert_json_response(response)
    assert response.json() == {"detail": "Debug mode is restricted to staff users."}
    assert captured.captured_queries == []
    assert SemanticQueryRun.objects.count() == 0


def test_staff_debug_success_contains_only_validated_plan_debug_surface(
    api_client: APIClient,
    staff_user,
    registered_orders: None,
) -> None:
    """Staff debug output is limited to the currently validated public plan."""

    api_client.force_authenticate(user=staff_user)
    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION, "plan": aggregate_plan(), "debug": True},
        format="json",
    )

    assert response.status_code == 200
    assert set(response.data["debug"]) == {"validated_plan"}
    assert response.data["debug"]["validated_plan"] == response.data["plan"]
    debug_text = json.dumps(response.data["debug"])
    assert PRIVATE_BINDING not in debug_text
    assert PRIVATE_PERMISSION not in debug_text

    run = SemanticQueryRun.objects.get(pk=response.data["run_id"])
    assert run.question == ""
    assert run.plan == {"resource": "orders", "intent": "aggregate"}
    assert run.status == SemanticQueryRun.Status.SUCCESS


def test_run_detail_characterizes_owner_staff_other_and_missing_distinction(
    api_client: APIClient,
    user,
    staff_user,
    registered_orders: None,
) -> None:
    """Run detail currently distinguishes an inaccessible run from a missing run."""

    other = get_user_model().objects.create_user(username="api-characterization-other")
    api_client.force_authenticate(user=user)
    query = api_client.post(
        "/asklens/query/",
        {"question": QUESTION, "plan": aggregate_plan()},
        format="json",
    )
    run = SemanticQueryRun.objects.get(pk=query.data["run_id"])
    path = f"/asklens/runs/{run.pk}/"

    owner_response = api_client.get(path)
    api_client.force_authenticate(user=staff_user)
    staff_response = api_client.get(path)
    api_client.force_authenticate(user=other)
    other_response = api_client.get(path)
    missing_response = api_client.get(f"/asklens/runs/{run.pk + 999_999}/")

    assert owner_response.status_code == 200
    assert staff_response.status_code == 200
    assert owner_response.data == staff_response.data
    assert set(owner_response.data) == {
        "id",
        "question",
        "plan",
        "status",
        "row_count",
        "duration_ms",
        "error",
        "created_at",
    }
    assert owner_response.data["question"] == ""
    assert owner_response.data["plan"] == {
        "resource": "orders",
        "intent": "aggregate",
    }
    assert owner_response.data["status"] == SemanticQueryRun.Status.SUCCESS
    assert "user" not in owner_response.data
    detail_text = str(owner_response.data)
    assert QUESTION not in detail_text
    assert PRIVATE_BINDING not in detail_text
    assert PRIVATE_PERMISSION not in detail_text

    assert other_response.status_code == 403
    assert_json_response(other_response)
    assert other_response.json() == {
        "detail": "You do not have access to this AskLens run."
    }
    assert missing_response.status_code == 404
    assert_json_response(missing_response)
    assert set(missing_response.json()) == {"detail"}
