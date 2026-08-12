"""API-4a regressions for the route-local AskLens error adapter."""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.authentication import BasicAuthentication
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView

from django_asklens.api.views import (
    CapabilitiesView,
    CatalogView,
    QueryRunDetailView,
    QueryView,
)
from django_asklens.models import SemanticQueryRun
from django_asklens.querying import AskLensQueryResponse

pytestmark = pytest.mark.django_db

AUTHORIZATION_ERROR = {
    "error": {
        "code": "asklens.authorization.denied",
        "message": "The current request is not authorized.",
    }
}
EXECUTION_ERROR = {
    "error": {
        "code": "asklens.execute.failed",
        "message": "The AskLens request could not be completed.",
    }
}
ROUTES = (
    ("catalog", "/asklens/catalog/", CatalogView, "get"),
    ("capabilities", "/asklens/capabilities/", CapabilitiesView, "get"),
    ("query", "/asklens/query/", QueryView, "post"),
    ("run-detail", "/asklens/runs/999999/", QueryRunDetailView, "get"),
)
ACCEPTED_ERRORS = (
    ("asklens.parse.invalid", "The query plan could not be parsed."),
    ("asklens.member.unavailable", "A requested query member is unavailable."),
    ("asklens.plan.invalid", "The query plan is invalid."),
    (
        "asklens.authorization.denied",
        "The current request is not authorized to execute this query.",
    ),
    (
        "asklens.scope.unavailable",
        "A safe query scope is unavailable for this request.",
    ),
    ("asklens.budget.exceeded", "The query plan exceeds an execution limit."),
    ("asklens.binding.invalid", "The query plan could not be bound safely."),
    ("asklens.compile.failed", "The query plan could not be compiled."),
    ("asklens.execute.failed", "The query could not be executed."),
    (
        "asklens.provider.failed",
        "The query provider could not produce a usable response.",
    ),
)


class HostAPIView(APIView):
    """A non-AskLens view proving the adapter is not installed globally."""

    authentication_classes = ()
    permission_classes = ()

    def get(self, request) -> Response:
        """Raise one ordinary host-owned DRF permission failure."""

        raise DRFPermissionDenied("Host endpoint detail remains host-owned.")


@pytest.fixture
def user():
    """Return one authenticated principal for adapter tests."""

    return get_user_model().objects.create_user(username="api4a-adapter-user")


@pytest.fixture
def api_client(user) -> APIClient:
    """Return an authenticated client."""

    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _request_route(client: APIClient, route_name: str, path: str):
    """Issue the route's supported request with a structurally valid body."""

    if route_name == "query":
        return client.post(path, {"question": "Synthetic question"}, format="json")
    return client.get(path)


def test_non_asklens_host_view_keeps_drf_exception_shape() -> None:
    """The AskLens adapter does not alter unrelated host DRF endpoints."""

    response = HostAPIView.as_view()(APIRequestFactory().get("/host/endpoint/"))

    assert response.status_code == 403
    assert response.data == {"detail": "Host endpoint detail remains host-owned."}


@pytest.mark.parametrize(("code", "message"), ACCEPTED_ERRORS)
def test_accepted_asklens_errors_keep_their_exact_error_child(
    api_client: APIClient,
    monkeypatch,
    code: str,
    message: str,
) -> None:
    """The HTTP adapter removes shared wrappers without rewriting AskLens errors."""

    error = {"code": code, "message": message, "pointer": "/safe-pointer"}
    outcome = AskLensQueryResponse(
        response_type="error",
        payload={
            "question": "Synthetic question",
            "status": "failed",
            "error": error,
        },
        status_code=400,
    )
    monkeypatch.setattr(
        "django_asklens.api.views.execute_asklens_query_request",
        lambda *args, **kwargs: outcome,
    )

    response = api_client.post(
        "/asklens/query/",
        {"question": "Synthetic question"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data == {"error": error}


def test_configured_authentication_denial_preserves_challenge_and_precedes_handler(
    monkeypatch,
) -> None:
    """A host authenticator retains its 401 challenge under the safe envelope."""

    def fail_handler(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Authentication denial must precede the route handler.")

    monkeypatch.setattr(CatalogView, "get", fail_handler)
    request = APIRequestFactory().get("/asklens/catalog/")

    with CaptureQueriesContext(connection) as captured:
        response = CatalogView.as_view(
            authentication_classes=(BasicAuthentication,),
        )(request)

    assert response.status_code == 401
    assert response.data == AUTHORIZATION_ERROR
    assert response["WWW-Authenticate"].startswith("Basic")
    assert captured.captured_queries == []
    assert SemanticQueryRun.objects.count() == 0


@pytest.mark.parametrize(
    "exception",
    (
        DRFPermissionDenied("private DRF permission diagnostic"),
        DjangoPermissionDenied("private Django permission diagnostic"),
    ),
    ids=("drf", "django"),
)
def test_permission_exceptions_use_fixed_authorization_error(
    api_client: APIClient,
    monkeypatch,
    exception: Exception,
) -> None:
    """Django and DRF permission diagnostics are never reflected."""

    def deny(*args: Any, **kwargs: Any) -> None:
        raise exception

    monkeypatch.setattr(CatalogView, "get", deny)

    with CaptureQueriesContext(connection) as captured:
        response = api_client.get("/asklens/catalog/")

    assert response.status_code == 403
    assert response.json() == AUTHORIZATION_ERROR
    assert "private" not in response.content.decode()
    assert captured.captured_queries == []
    assert SemanticQueryRun.objects.count() == 0


@pytest.mark.parametrize(
    ("route_name", "path", "view_class", "handler"),
    ROUTES,
    ids=[case[0] for case in ROUTES],
)
def test_unexpected_route_errors_are_fixed_safe_and_route_local(
    route_name: str,
    path: str,
    view_class,
    handler: str,
    api_client: APIClient,
    monkeypatch,
) -> None:
    """Unexpected failures in each AskLens view return one safe 500 envelope."""

    private_diagnostic = f"private-{route_name}-unexpected-diagnostic"

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError(private_diagnostic)

    monkeypatch.setattr(view_class, handler, fail)

    with CaptureQueriesContext(connection) as captured:
        response = _request_route(api_client, route_name, path)

    assert response.status_code == 500
    assert response.json() == EXECUTION_ERROR
    assert private_diagnostic not in response.content.decode()
    assert captured.captured_queries == []
    assert SemanticQueryRun.objects.count() == 0
