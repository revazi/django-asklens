"""Tests for the runnable AskLens demo frontend page."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, override_settings

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
    assert 'data-query-url="/asklens/query/"' in content
    assert "Show paid billing revenue by product" in content
    assert "Tenant row scope" in content
    assert "North Studio" in content
    assert "Display as" in content
    assert "Raw JSON" in content
