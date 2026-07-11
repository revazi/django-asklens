"""Tests for the runnable AskLens demo frontend page."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, override_settings

from django_asklens.frontend.views import asklens_frontend
from tests.test_project.demo_views import asklens_demo
from tests.test_project.models import Facility, StaffAssignment, StaffGrant

pytestmark = pytest.mark.django_db

TEMPLATE_SETTINGS = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    }
]


def test_demo_frontend_redirects_anonymous_user() -> None:
    """Anonymous visitors are sent to the demo admin login."""

    request = RequestFactory().get("/")
    request.user = AnonymousUser()

    response = asklens_demo(request)

    assert response.status_code == 302
    assert response.url == "/admin/login/?next=/"


def deny_frontend_access(_request) -> bool:
    """Permission-check helper for packaged frontend tests."""

    return False


@override_settings(TEMPLATES=TEMPLATE_SETTINGS)
def test_packaged_frontend_defaults_to_authenticated_users() -> None:
    """Projects can mount the packaged frontend without demo-only code."""

    anonymous_request = RequestFactory().get("/asklens/ui/")
    anonymous_request.user = AnonymousUser()

    anonymous_response = asklens_frontend(anonymous_request)

    assert anonymous_response.status_code == 302

    user = get_user_model().objects.create_user(username="regular", password="pw")
    request = RequestFactory().get("/asklens/ui/")
    request.user = user

    response = asklens_frontend(request)
    content = response.content.decode()

    assert response.status_code == 200
    assert "AskLens" in content
    assert 'data-query-url="/asklens/query/"' in content
    assert "Ask AskLens" in content


@override_settings(
    TEMPLATES=TEMPLATE_SETTINGS,
    DJANGO_ASKLENS={"FRONTEND_PERMISSION_CHECK": deny_frontend_access},
)
def test_packaged_frontend_supports_project_permission_check() -> None:
    """Projects can restrict the built-in frontend to selected users."""

    user = get_user_model().objects.create_user(username="regular", password="pw")
    request = RequestFactory().get("/asklens/ui/")
    request.user = user

    with pytest.raises(PermissionDenied):
        asklens_frontend(request)


def test_demo_frontend_denies_staff_user_without_reporting_grants() -> None:
    """A staff login alone is not enough to load the demo frontend."""

    user = get_user_model().objects.create_user(
        username="no-report",
        password="pw",
        is_staff=True,
    )
    request = RequestFactory().get("/")
    request.user = user

    with pytest.raises(PermissionDenied):
        asklens_demo(request)


@override_settings(TEMPLATES=TEMPLATE_SETTINGS)
def test_demo_frontend_renders_for_reporting_user() -> None:
    """A user with synthetic reporting grants can load the page shell."""

    user = get_user_model().objects.create_user(
        username="north-billing",
        password="pw",
        is_staff=True,
    )
    facility = Facility.objects.create(name="North Studio", slug="north-studio")
    assignment = StaffAssignment.objects.create(
        user=user,
        facility=facility,
        role=StaffAssignment.Role.STAFF,
    )
    StaffGrant.objects.create(
        assignment=assignment,
        name=StaffGrant.BILLING_REPORTS_VIEW,
    )

    request = RequestFactory().get("/")
    request.user = user

    response = asklens_demo(request)
    content = response.content.decode()

    assert response.status_code == 200
    assert "Django AskLens Demo" in content
    assert 'data-catalog-url="/asklens/catalog/"' in content
    assert 'data-capabilities-url="/asklens/capabilities/"' in content
    assert 'data-query-url="/asklens/query/"' in content
    assert "Ask AskLens" in content
    assert "Saved queries" in content
    assert "Saved locally in this browser" in content
    assert "No saved queries yet" in content
    assert "Save query" in content
    assert "AskLens is working" in content
    assert "Running…" in content
    assert "Suggestions" in content
    assert "Starter questions" in content
    assert "Visible capabilities" in content
    assert "Offline dummy plans" in content
    assert "dummy" in content
    assert "Show paid billing revenue by product" in content
    assert "Count member subscriptions by plan and status" not in content
    assert "Show scheduled capacity by session type" not in content
    assert "LLM help" in content
    assert "Deterministic fallback help" in content
    assert "Reason:" in content
    assert "Tenant row scope" in content
    assert "North Studio" in content
    assert "Raw response" in content
    assert content.index("Session") < content.index("Tenant row scope")
    assert content.index("Tenant row scope") < content.index("Saved queries")
    assert content.index("Saved queries") < content.index("Suggestions")
    assert content.index("Suggestions") < content.index("Visible capabilities")
    assert (
        '<details class="card disclosure" aria-label="Visible capabilities">' in content
    )


@override_settings(
    TEMPLATES=TEMPLATE_SETTINGS,
    DJANGO_ASKLENS={
        "LLM_BACKEND": "openai_compatible",
        "LLM_MODEL": "test-model",
        "LLM_API_KEY": "secret-test-key",
    },
)
def test_demo_frontend_renders_live_llm_status_without_secret() -> None:
    """Live demo mode should be visible without leaking provider secrets."""

    user = get_user_model().objects.create_user(
        username="north-billing",
        password="pw",
        is_staff=True,
    )
    facility = Facility.objects.create(name="North Studio", slug="north-studio")
    assignment = StaffAssignment.objects.create(
        user=user,
        facility=facility,
        role=StaffAssignment.Role.STAFF,
    )
    StaffGrant.objects.create(
        assignment=assignment,
        name=StaffGrant.BILLING_REPORTS_VIEW,
    )

    request = RequestFactory().get("/")
    request.user = user

    response = asklens_demo(request)
    content = response.content.decode()

    assert response.status_code == 200
    assert "Live LLM enabled" in content
    assert "openai_compatible" in content
    assert "test-model" in content
    assert "secret-test-key" not in content
