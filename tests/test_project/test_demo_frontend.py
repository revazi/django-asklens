"""Tests for the runnable AskLens demo frontend page."""

import re

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.test import RequestFactory, override_settings
from rest_framework.test import APIClient

from django_asklens.frontend.views import asklens_frontend
from django_asklens.models import SemanticQueryRun
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


DENIAL_PRIVATE_TEXT = (
    "no-report",
    "north studio",
    "south studio",
    "resource",
    "report",
    "grant",
    "permission",
    "membership",
    "tenant",
    "scope",
    "binding",
    "row",
    "diagnostic",
)


def check_recovery_csrf(token: str | None, secret: str | None) -> HttpResponse | None:
    """Exercise Django's CSRF gate for the recovery POST without logging out."""

    data = {} if token is None else {"csrfmiddlewaretoken": token}
    request = RequestFactory().post("/admin/logout/", data)
    if secret is not None:
        request.COOKIES[settings.CSRF_COOKIE_NAME] = secret
    middleware = CsrfViewMiddleware(lambda _request: HttpResponse())
    middleware.process_request(request)
    return middleware.process_view(request, lambda _request: HttpResponse(), (), {})


def assert_denial_content_is_opaque(content: str, csrf_secret: str) -> str:
    """Exclude only one valid CSRF field value, never other response content."""

    fields = list(
        re.finditer(
            r'<input type="hidden" name="csrfmiddlewaretoken" '
            r'value="([A-Za-z0-9]{64})">',
            content,
        )
    )
    assert len(fields) == 1
    field = fields[0]
    token = field.group(1)
    assert check_recovery_csrf(token, csrf_secret) is None
    public_content = content[: field.start(1)] + content[field.end(1) :]
    for forbidden in DENIAL_PRIVATE_TEXT:
        assert forbidden not in public_content.lower()
    return token


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
    assert "Read-only answers from approved data." in content
    assert 'id="asklens-scope-labels"' not in content
    assert 'id="scope-list"' not in content
    assert "Visible row scope" not in content
    assert "Operational run metadata is stored" not in content
    assert "question, complete plan, and result rows are omitted" not in content


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


@override_settings(
    ROOT_URLCONF="tests.test_project.demo_urls",
    TEMPLATES=TEMPLATE_SETTINGS,
)
@pytest.mark.parametrize("csrf_marker", ["row", "report", "permission"])
def test_demo_frontend_denial_is_opaque_with_csrf_post_recovery(
    monkeypatch, csrf_marker: str
) -> None:
    """A denied demo login gets one neutral, CSRF-protected recovery action."""

    monkeypatch.setattr(
        "django.middleware.csrf._get_new_csrf_string",
        lambda: csrf_marker.ljust(32, "a"),
    )
    user = get_user_model().objects.create_user(
        username="no-report",
        password="pw",
        is_staff=True,
    )
    request = RequestFactory().get("/")
    request.user = user

    response = asklens_demo(request)
    content = response.content.decode()

    assert response.status_code == 403
    assert "Access unavailable" in content
    assert "This page is not available for this account." in content
    assert '<form method="post" action="/admin/logout/">' in content
    assert 'name="csrfmiddlewaretoken"' in content
    assert 'name="next" value="/admin/login/?next=/"' in content
    assert "Sign out and switch account" in content
    token = assert_denial_content_is_opaque(content, request.META["CSRF_COOKIE"])
    assert csrf_marker in token


@pytest.mark.parametrize(
    "wrapper",
    ["<p>{}</p>", '<div title="{}"></div>', "<!-- {} -->", '<input value="{}">'],
)
def test_denial_privacy_assertion_still_rejects_content_outside_csrf(
    wrapper: str,
) -> None:
    """Token filtering cannot hide body, attribute, comment, or other input leaks."""

    token = "row".ljust(32, "a") * 2
    field = f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}">'
    assert assert_denial_content_is_opaque(field, "a" * 32) == token
    for private_text in (*DENIAL_PRIVATE_TEXT, token):
        with pytest.raises(AssertionError):
            assert_denial_content_is_opaque(
                field + wrapper.format(private_text), "a" * 32
            )


@pytest.mark.parametrize("field_count", [0, 2])
def test_denial_privacy_assertion_requires_exactly_one_csrf_field(
    field_count: int,
) -> None:
    """Missing or duplicated CSRF fields are not silently normalized away."""

    token = "row".ljust(32, "a") * 2
    field = f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}">'
    with pytest.raises(AssertionError):
        assert_denial_content_is_opaque(field * field_count, "a" * 32)


@pytest.mark.parametrize("token", ["not-a-token", "a" * 32 + "b" * 32])
def test_denial_privacy_assertion_rejects_invalid_csrf_values(token: str) -> None:
    """Format alone cannot authorize excluding an arbitrary field value."""

    field = f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}">'
    with pytest.raises(AssertionError):
        assert_denial_content_is_opaque(field, "a" * 32)


@pytest.mark.parametrize(
    ("token", "secret"),
    [(None, "a" * 32), ("a" * 32 + "b" * 32, "a" * 32), ("a" * 64, None)],
)
def test_recovery_csrf_gate_rejects_missing_or_mismatched_credentials(
    token: str | None, secret: str | None
) -> None:
    """The real middleware rejects absent tokens/cookies and incorrect tokens."""

    response = check_recovery_csrf(token, secret)
    assert response is not None
    assert response.status_code == 403


def test_no_report_api_denial_stays_opaque_and_unaudited(settings) -> None:
    """Demo route recovery does not alter API denial envelopes or auditing."""

    settings.DJANGO_ASKLENS = {
        "API_PERMISSION_CLASSES": [
            "tests.test_project.permissions.CanUseComplexAnalytics",
        ],
        "REQUEST_PERMISSIONS_GETTER": (
            "tests.test_project.permissions.get_request_permissions"
        ),
        "AUDIT_MODE": "database",
        "AUDIT_INCLUDE_CONTENT": False,
    }
    user = get_user_model().objects.create_user(
        username="no-report",
        password="pw",
        is_staff=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/asklens/query/",
        {"question": "private denial question"},
        format="json",
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "asklens.authorization.denied",
            "message": "The current request is not authorized.",
        }
    }
    assert "private denial question" not in response.content.decode()
    assert SemanticQueryRun.objects.count() == 0


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
    assert "AskLens" in content
    assert "Django AskLens Demo" not in content
    assert "Synthetic demo data." in content
    assert 'data-catalog-url="/asklens/catalog/"' in content
    assert 'data-capabilities-url="/asklens/capabilities/"' in content
    assert 'data-query-url="/asklens/query/"' in content
    assert "Read-only answers from approved data." in content
    assert "Saved queries" in content
    assert "Saved in this browser" in content
    assert "No saved queries yet" in content
    assert "Save query" in content
    assert ">Clear</button>" in content
    assert "Clear saved" not in content
    assert "Working…" in content
    assert 'id="clear-chat-button"' in content
    assert "Clear chat" in content
    assert 'aria-label="Send question"' in content
    assert 'class="sr-only send-label"' in content
    assert "Running…" not in content
    assert "Suggestions" in content
    assert "Starter questions" in content
    assert "Visible catalog" in content
    assert "Queryable resources" in content
    assert "Resources visible to you." in content
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
    assert "South Studio" not in content
    assert (
        "This context is supplied by the server. Current authorization and row "
        "scope are rechecked for every execution; these labels do not grant access."
        in content
    )
    assert (
        '<section class="card scope-context" aria-label="Tenant row scope">' in content
    )
    assert "Operational run metadata is stored" in content
    assert "question, complete plan, and result rows are omitted" in content
    assert "Raw response" in content
    assert "Limit:" in content
    assert "Truncated:" in content
    assert "Truncation applies only to this current authorized query." in content
    assert (
        "A yes value means additional matching rows or groups were detected" in content
    )
    assert "the returned result." in content
    assert (
        '<details class="card disclosure session-disclosure" '
        'aria-label="Current session">' in content
    )
    assert 'class="tag-strip" aria-label="Session summary"' not in content
    assert 'id="capabilities-status"' not in content
    assert "capabilities.summary" not in content
    assert "payload?.error?.message || response.statusText" in content
    assert "payload?.detail" not in content
    assert "payload = { detail: text }" not in content
    assert content.index("Tenant row scope") < content.index("Session")
    assert content.index("Session") < content.index("Saved queries")
    assert content.index("Saved queries") < content.index("Suggestions")
    assert content.index("Suggestions") < content.index("Visible catalog")
    assert '<details class="card disclosure" aria-label="Visible catalog">' in content


@pytest.mark.parametrize(
    "audit_settings",
    [
        {"AUDIT_MODE": "disabled", "AUDIT_INCLUDE_CONTENT": False},
        {"AUDIT_MODE": "database", "AUDIT_INCLUDE_CONTENT": True},
        {"AUDIT_MODE": "custom", "AUDIT_INCLUDE_CONTENT": False},
    ],
)
@override_settings(TEMPLATES=TEMPLATE_SETTINGS)
def test_demo_frontend_omits_audit_notice_outside_metadata_only_database_mode(
    settings,
    audit_settings,
) -> None:
    """Demo audit wording appears only for the policy it accurately describes."""

    settings.DJANGO_ASKLENS = audit_settings
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
    assert "Operational run metadata is stored" not in content
    assert "question, complete plan, and result rows are omitted" not in content


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
    assert "<code>openai_compatible</code> · <code>test-model</code>" not in content
    assert '<span class="pill"><code>openai_compatible</code></span>' in content
    assert '<span class="pill"><code>test-model</code></span>' in content
    assert "secret-test-key" not in content
