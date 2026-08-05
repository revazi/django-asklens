"""Integration tests for the view-only AskLens audit admin."""

from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory
from django.urls import clear_url_caches, reverse

from django_asklens.models import SemanticQueryRun

ADMIN_INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "rest_framework",
    "django_asklens",
    "tests.test_project.apps.TestProjectConfig",
]
ADMIN_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ADMIN_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]


@pytest.fixture(autouse=True)
def admin_test_settings(settings):
    """Enable only the test-time Django admin request stack."""

    settings.ROOT_URLCONF = "tests.admin_urls"
    settings.INSTALLED_APPS = ADMIN_INSTALLED_APPS
    settings.MIDDLEWARE = ADMIN_MIDDLEWARE
    settings.TEMPLATES = ADMIN_TEMPLATES
    settings.SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
    settings.MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
    clear_url_caches()
    yield
    clear_url_caches()


@pytest.fixture
def audit_run(db) -> SemanticQueryRun:
    """Create one synthetic built-in database audit row."""

    return SemanticQueryRun.objects.create(
        question="synthetic audit question",
        plan={"resource": "synthetic", "intent": "list"},
        status=SemanticQueryRun.Status.SUCCESS,
        row_count=1,
        duration_ms=2,
    )


def _staff_user(*permissions: str, superuser: bool = False):
    user = get_user_model().objects.create_user(
        username=f"audit-admin-{get_user_model().objects.count()}",
        is_staff=True,
        is_superuser=superuser,
    )
    if permissions:
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="asklens",
                codename__in=permissions,
            )
        )
    return user


def _audit_admin():
    return admin.site._registry[SemanticQueryRun]


@pytest.mark.django_db
def test_audit_admin_denies_all_mutation_permissions_for_superuser() -> None:
    """Even a superuser must receive a view-only audit admin surface."""

    request = RequestFactory().get("/admin/asklens/semanticqueryrun/")
    request.user = _staff_user(superuser=True)
    model_admin = _audit_admin()

    assert model_admin.has_view_permission(request) is True
    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission",
    ["view_semanticqueryrun", "change_semanticqueryrun"],
)
def test_audit_admin_preserves_inherited_view_semantics(
    client,
    audit_run: SemanticQueryRun,
    permission: str,
) -> None:
    """Django's inherited raw view-or-change permission still grants viewing."""

    client.force_login(_staff_user(permission))

    changelist = client.get(reverse("admin:asklens_semanticqueryrun_changelist"))
    detail = client.get(
        reverse("admin:asklens_semanticqueryrun_change", args=[audit_run.pk])
    )

    assert changelist.status_code == 200
    assert detail.status_code == 200


@pytest.mark.django_db
def test_audit_admin_detail_is_view_only_for_superuser(
    client,
    audit_run: SemanticQueryRun,
) -> None:
    """The audit detail remains readable without save or delete controls."""

    client.force_login(_staff_user(superuser=True))

    response = client.get(
        reverse("admin:asklens_semanticqueryrun_change", args=[audit_run.pk])
    )

    assert response.status_code == 200
    assert b'name="_save"' not in response.content
    assert b'name="_continue"' not in response.content
    assert b'name="_addanother"' not in response.content
    assert b'class="deletelink"' not in response.content


@pytest.mark.django_db
def test_audit_admin_has_no_bulk_delete_action(client, audit_run) -> None:
    """Django must filter delete_selected from the audit changelist."""

    user = _staff_user(superuser=True)
    client.force_login(user)

    response = client.get(reverse("admin:asklens_semanticqueryrun_changelist"))
    request = RequestFactory().get("/admin/asklens/semanticqueryrun/")
    request.user = user

    assert response.status_code == 200
    assert "delete_selected" not in _audit_admin().get_actions(request)
    assert b'value="delete_selected"' not in response.content


@pytest.mark.django_db
def test_audit_admin_direct_add_is_forbidden(client) -> None:
    """A forged add request cannot create an audit row."""

    client.force_login(_staff_user(superuser=True))
    before = SemanticQueryRun.objects.count()
    url = reverse("admin:asklens_semanticqueryrun_add")

    get_response = client.get(url)
    post_response = client.post(
        url,
        {
            "question": "forged question",
            "plan": "{}",
            "status": SemanticQueryRun.Status.SUCCESS,
            "row_count": 1,
        },
    )

    assert get_response.status_code == 403
    assert post_response.status_code == 403
    assert SemanticQueryRun.objects.count() == before


@pytest.mark.django_db
def test_audit_admin_direct_change_is_forbidden(
    client,
    audit_run: SemanticQueryRun,
) -> None:
    """A forged superuser change POST is denied and cannot alter content."""

    client.force_login(_staff_user(superuser=True))
    original_question = audit_run.question
    url = reverse("admin:asklens_semanticqueryrun_change", args=[audit_run.pk])

    with patch.object(_audit_admin(), "log_change"):
        response = client.post(
            url,
            {
                "question": "forged replacement",
                "plan": "{}",
                "status": SemanticQueryRun.Status.FAILED,
                "row_count": 0,
            },
        )

    audit_run.refresh_from_db()
    assert response.status_code == 403
    assert audit_run.question == original_question
    assert audit_run.status == SemanticQueryRun.Status.SUCCESS
    assert audit_run.row_count == 1


@pytest.mark.django_db
def test_audit_admin_direct_delete_is_forbidden(
    client,
    audit_run: SemanticQueryRun,
) -> None:
    """Direct audit delete GET/POST requests are denied without deletion."""

    client.force_login(_staff_user(superuser=True))
    url = reverse("admin:asklens_semanticqueryrun_delete", args=[audit_run.pk])

    with patch.object(_audit_admin(), "log_deletions"):
        get_response = client.get(url)
        post_response = client.post(url, {"post": "yes"})

    assert get_response.status_code == 403
    assert post_response.status_code == 403
    assert SemanticQueryRun.objects.filter(pk=audit_run.pk).exists()


@pytest.mark.django_db
def test_audit_admin_forged_bulk_delete_cannot_mutate(
    client,
    audit_run: SemanticQueryRun,
) -> None:
    """A forged delete_selected POST is filtered and leaves rows intact."""

    client.force_login(_staff_user(superuser=True))
    url = reverse("admin:asklens_semanticqueryrun_changelist")

    with patch.object(_audit_admin(), "log_deletions"):
        response = client.post(
            url,
            {
                "action": "delete_selected",
                "_selected_action": [str(audit_run.pk)],
                "post": "yes",
                "index": "0",
            },
        )

    assert response.status_code in {200, 302}
    assert SemanticQueryRun.objects.filter(pk=audit_run.pk).exists()
