"""DRF transport hardening tests for AskLens query entry points."""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.throttling import BaseThrottle

from django_asklens.api.views import QueryView

pytestmark = pytest.mark.django_db


class QueryThrottleDenyAll(BaseThrottle):
    """Deterministic throttle that always rejects requests."""

    def allow_request(self, request: Request, view: QueryView) -> bool:
        return False

    def wait(self) -> float | None:
        return None


@pytest.fixture
def throttled_query_user() -> object:
    """Return a deterministic authenticated principal for API tests."""

    return get_user_model().objects.create_user(username="throttle", password="pw")


def test_query_view_throttle_blocks_before_facade_and_audit(
    settings,
    monkeypatch,
    throttled_query_user: object,
) -> None:
    """A deterministic DRF throttle blocks `QueryView` before facade/audit."""

    events = []

    def sink(event: dict) -> None:
        events.append(event)

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "custom",
        "AUDIT_SINK": sink,
        "AUDIT_INCLUDE_CONTENT": False,
    }

    facade_calls = {"executed": False}

    def fail_if_called(*args, **kwargs) -> None:
        facade_calls["executed"] = True
        raise AssertionError("AskLens facade should not run on a throttled request.")

    monkeypatch.setattr(
        "django_asklens.api.views.execute_asklens_query_request",
        fail_if_called,
    )

    request = APIRequestFactory().post(
        "/asklens/query/",
        {"question": "Show orders by status"},
        format="json",
    )
    force_authenticate(request, user=throttled_query_user)

    with CaptureQueriesContext(connection) as captured:
        response = QueryView.as_view(throttle_classes=(QueryThrottleDenyAll,))(request)

    assert response.status_code == 429
    assert facade_calls["executed"] is False
    assert events == []
    assert len(captured) == 0
