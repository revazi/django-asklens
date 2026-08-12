"""API-5 regression coverage for run-detail and database-audit privacy."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection, connections
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from django_asklens import Metric
from django_asklens.api.views import QueryRunDetailView
from django_asklens.catalog.registry import default_registry
from django_asklens.models import SemanticQueryRun
from tests.test_project.models import Order

pytestmark = pytest.mark.django_db

AUDIT_PERMISSION = "asklens.view_semanticqueryrun"
AUDIT_TABLE = "asklens_semanticqueryrun"
QUESTION = "Synthetic operational question"


@pytest.fixture(autouse=True)
def isolate_registry() -> None:
    """Keep API-5 registrations isolated from the rest of the suite."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Return a DRF client for run-detail assertions."""

    return APIClient()


@pytest.fixture
def owner():
    """Return the owner of synthetic audit rows."""

    return get_user_model().objects.create_user(username="api5-owner")


@pytest.fixture
def other_user():
    """Return a regular non-owner without audit-view permission."""

    return get_user_model().objects.create_user(username="api5-other")


@pytest.fixture
def audit_run(owner) -> SemanticQueryRun:
    """Create one metadata-only synthetic audit row."""

    return SemanticQueryRun.objects.create(
        user=owner,
        question="",
        plan={"resource": "orders", "intent": "aggregate"},
        status=SemanticQueryRun.Status.SUCCESS,
        row_count=1,
    )


@pytest.fixture
def registered_orders() -> None:
    """Register one global synthetic resource for database-audit writes."""

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
            }
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
    )


def aggregate_plan() -> dict[str, object]:
    """Return one deterministic aggregate plan."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "metrics": [{"metric": "order_count"}],
        "limit": 10,
    }


def grant_audit_view_permission(user) -> None:
    """Grant Django's global AskLens audit-view permission."""

    permission = Permission.objects.get(
        content_type__app_label="asklens",
        codename="view_semanticqueryrun",
    )
    user.user_permissions.add(permission)


def audit_sql(queries: list[dict[str, str]]) -> list[str]:
    """Return statements that target the built-in audit table."""

    return [query["sql"] for query in queries if AUDIT_TABLE in query["sql"].lower()]


def test_run_detail_owner_can_view_own_run(
    api_client: APIClient,
    owner,
    audit_run: SemanticQueryRun,
) -> None:
    """The owning authenticated principal retains access."""

    api_client.force_authenticate(user=owner)

    response = api_client.get(f"/asklens/runs/{audit_run.pk}/")

    assert response.status_code == 200
    assert response.data["id"] == audit_run.pk


def test_run_detail_staff_without_permission_gets_opaque_404(
    api_client: APIClient,
    audit_run: SemanticQueryRun,
) -> None:
    """Staff status alone does not grant cross-user audit access."""

    staff = get_user_model().objects.create_user(username="api5-staff", is_staff=True)
    assert not staff.has_perm(AUDIT_PERMISSION)
    api_client.force_authenticate(user=staff)

    response = api_client.get(f"/asklens/runs/{audit_run.pk}/")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "asklens.member.unavailable",
            "message": "A requested query member is unavailable.",
        }
    }


def test_run_detail_explicit_view_permission_allows_cross_user_review(
    api_client: APIClient,
    audit_run: SemanticQueryRun,
) -> None:
    """The explicit global Django view permission grants audit review."""

    reviewer = get_user_model().objects.create_user(username="api5-reviewer")
    grant_audit_view_permission(reviewer)
    assert reviewer.has_perm(AUDIT_PERMISSION)
    api_client.force_authenticate(user=reviewer)

    response = api_client.get(f"/asklens/runs/{audit_run.pk}/")

    assert response.status_code == 200
    assert response.data["id"] == audit_run.pk


def test_run_detail_superuser_follows_normal_django_permission_behavior(
    api_client: APIClient,
    audit_run: SemanticQueryRun,
) -> None:
    """An active superuser receives Django's normal global permission result."""

    superuser = get_user_model().objects.create_superuser(
        username="api5-superuser",
        password="synthetic-password",
    )
    assert superuser.has_perm(AUDIT_PERMISSION)
    api_client.force_authenticate(user=superuser)

    response = api_client.get(f"/asklens/runs/{audit_run.pk}/")

    assert response.status_code == 200
    assert response.data["id"] == audit_run.pk


def test_run_detail_anonymous_and_configured_route_gates_still_run_first(
    settings,
    api_client: APIClient,
    owner,
    audit_run: SemanticQueryRun,
    monkeypatch,
) -> None:
    """DRF authentication and configured route policy precede run lookup."""

    def fail_handler(*args, **kwargs):
        raise AssertionError("Route denial must precede the run-detail handler.")

    monkeypatch.setattr(QueryRunDetailView, "get", fail_handler)
    anonymous = api_client.get(f"/asklens/runs/{audit_run.pk}/")
    assert anonymous.status_code == 403
    assert SemanticQueryRun.objects.count() == 1

    settings.DJANGO_ASKLENS = {
        "API_PERMISSION_CLASSES": [
            "tests.test_project.permissions.DenyAskLensAccess",
        ]
    }
    api_client.force_authenticate(user=owner)
    configured_denial = api_client.get(f"/asklens/runs/{audit_run.pk}/")

    assert configured_denial.status_code == 403
    assert configured_denial.json() == {
        "error": {
            "code": "asklens.authorization.denied",
            "message": "The current request is not authorized.",
        }
    }
    assert SemanticQueryRun.objects.count() == 1


def test_run_detail_inaccessible_and_missing_are_one_query_opaque_404s_without_audit(
    api_client: APIClient,
    other_user,
    audit_run: SemanticQueryRun,
) -> None:
    """Authorization-filtered lookup hides existence and does not audit reads."""

    assert not other_user.has_perm(AUDIT_PERMISSION)
    api_client.force_authenticate(user=other_user)
    paths = (
        f"/asklens/runs/{audit_run.pk}/",
        f"/asklens/runs/{audit_run.pk + 999_999}/",
    )
    responses = []

    for path in paths:
        before = SemanticQueryRun.objects.count()
        with CaptureQueriesContext(connection) as captured:
            response = api_client.get(path)
        responses.append(response)
        assert len(captured.captured_queries) == 1
        assert captured.captured_queries[0]["sql"].lstrip().upper().startswith("SELECT")
        assert SemanticQueryRun.objects.count() == before

    assert [response.status_code for response in responses] == [404, 404]
    assert [response.json() for response in responses] == [
        {
            "error": {
                "code": "asklens.member.unavailable",
                "message": "A requested query member is unavailable.",
            }
        },
        {
            "error": {
                "code": "asklens.member.unavailable",
                "message": "A requested query member is unavailable.",
            }
        },
    ]


@pytest.mark.parametrize(
    "configured_content",
    [False, "true"],
    ids=["off", "malformed"],
)
def test_run_detail_metadata_policy_sanitizes_full_content_legacy_row(
    settings,
    api_client: APIClient,
    owner,
    configured_content,
) -> None:
    """Display redacts stored full content unless the current setting is True."""

    settings.DJANGO_ASKLENS = {"AUDIT_INCLUDE_CONTENT": configured_content}
    run = SemanticQueryRun.objects.create(
        user=owner,
        question="Synthetic retained question",
        plan={
            "resource": "orders",
            "intent": "list",
            "filters": [
                {
                    "field": "internal_note",
                    "op": "eq",
                    "value": "synthetic-private-value",
                }
            ],
            "binding": "customer__internal_note",
            "permission": "synthetic.view_internal_note",
            "tenant_id": "synthetic-tenant-id",
            "rows": [{"internal_note": "synthetic-private-row"}],
            "provider_payload": {"content": "synthetic-provider-content"},
            "credential": "synthetic-credential",
        },
        status=SemanticQueryRun.Status.SUCCESS,
    )
    api_client.force_authenticate(user=owner)

    response = api_client.get(f"/asklens/runs/{run.pk}/")

    assert response.status_code == 200
    assert response.data["question"] == ""
    assert response.data["plan"] == {"resource": "orders", "intent": "list"}
    response_text = json.dumps(response.data)
    for private_value in (
        "Synthetic retained question",
        "internal_note",
        "synthetic-private-value",
        "customer__internal_note",
        "synthetic.view_internal_note",
        "synthetic-tenant-id",
        "synthetic-private-row",
        "synthetic-provider-content",
        "synthetic-credential",
    ):
        assert private_value not in response_text


def test_run_detail_explicit_full_content_policy_returns_stored_question_and_plan(
    settings,
    api_client: APIClient,
    owner,
) -> None:
    """Boolean True permits authorized access to host-retained full content."""

    settings.DJANGO_ASKLENS = {"AUDIT_INCLUDE_CONTENT": True}
    stored_plan = {
        "resource": "orders",
        "intent": "list",
        "filters": [{"field": "status", "op": "eq", "value": "paid"}],
        "select": ["id"],
        "limit": 10,
    }
    run = SemanticQueryRun.objects.create(
        user=owner,
        question=QUESTION,
        plan=stored_plan,
        status=SemanticQueryRun.Status.SUCCESS,
    )
    api_client.force_authenticate(user=owner)

    response = api_client.get(f"/asklens/runs/{run.pk}/")

    assert response.status_code == 200
    assert response.data["question"] == QUESTION
    assert response.data["plan"] == stored_plan


@pytest.mark.parametrize(
    ("status", "stored_error", "expected"),
    [
        (
            SemanticQueryRun.Status.FAILED,
            "asklens.member.unavailable: A requested query member is unavailable.",
            {
                "code": "asklens.member.unavailable",
                "message": "A requested query member is unavailable.",
            },
        ),
        (
            SemanticQueryRun.Status.FAILED,
            "asklens.member.unavailable: synthetic private diagnostic",
            {
                "code": "asklens.execute.failed",
                "message": "The query could not be executed.",
            },
        ),
        (
            SemanticQueryRun.Status.FAILED,
            "host.failure: synthetic private diagnostic",
            {
                "code": "asklens.execute.failed",
                "message": "The query could not be executed.",
            },
        ),
        (SemanticQueryRun.Status.FAILED, "", None),
        (
            SemanticQueryRun.Status.SUCCESS,
            "asklens.member.unavailable: synthetic private diagnostic",
            None,
        ),
    ],
    ids=["known", "malformed-known", "unknown", "blank", "success"],
)
def test_run_detail_returns_only_structured_safe_audit_errors(
    api_client: APIClient,
    owner,
    status: str,
    stored_error: str,
    expected,
) -> None:
    """Stored free-form text is never reflected through run detail."""

    run = SemanticQueryRun.objects.create(
        user=owner,
        question="",
        plan={},
        status=status,
        error=stored_error,
    )
    api_client.force_authenticate(user=owner)

    response = api_client.get(f"/asklens/runs/{run.pk}/")

    assert response.status_code == 200
    assert response.data["error"] == expected
    assert "synthetic private diagnostic" not in json.dumps(response.data)
    assert "host.failure" not in json.dumps(response.data)


@pytest.mark.django_db(transaction=True, databases=["default", "asklens_read"])
def test_configured_alias_controls_database_audit_write_and_read_without_client_input(
    settings,
    api_client: APIClient,
    owner,
    registered_orders: None,
) -> None:
    """Server-owned alternate alias is used for both write and detail read."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "database",
        "AUDIT_INCLUDE_CONTENT": False,
        "AUDIT_DATABASE_ALIAS": "asklens_read",
    }
    api_client.force_authenticate(user=owner)

    with (
        CaptureQueriesContext(connections["default"]) as default_write_queries,
        CaptureQueriesContext(connections["asklens_read"]) as alias_write_queries,
    ):
        query = api_client.post(
            "/asklens/query/",
            {
                "question": QUESTION,
                "plan": aggregate_plan(),
            },
            format="json",
        )

    assert query.status_code == 200
    assert "run_id" in query.data
    assert audit_sql(default_write_queries.captured_queries) == []
    alias_audit_writes = audit_sql(alias_write_queries.captured_queries)
    assert len(alias_audit_writes) == 1
    assert alias_audit_writes[0].lstrip().upper().startswith("INSERT")

    assert not owner.has_perm(AUDIT_PERMISSION)
    with (
        CaptureQueriesContext(connections["default"]) as default_read_queries,
        CaptureQueriesContext(connections["asklens_read"]) as alias_read_queries,
    ):
        detail = api_client.get(f"/asklens/runs/{query.data['run_id']}/")

    assert detail.status_code == 200
    assert detail.data["id"] == query.data["run_id"]
    assert audit_sql(default_read_queries.captured_queries) == []
    alias_audit_reads = audit_sql(alias_read_queries.captured_queries)
    assert len(alias_audit_reads) == 1
    assert alias_audit_reads[0].lstrip().upper().startswith("SELECT")


@pytest.mark.parametrize(
    "malformed_alias",
    ["", " asklens_read", 7],
    ids=["empty", "whitespace", "non-string"],
)
def test_malformed_audit_alias_returns_fixed_safe_detail_response(
    settings,
    api_client: APIClient,
    owner,
    malformed_alias,
) -> None:
    """Malformed server-owned aliases fail closed without ordinary routing."""

    run = SemanticQueryRun.objects.create(
        user=owner,
        question="",
        plan={},
        status=SemanticQueryRun.Status.SUCCESS,
    )
    settings.DJANGO_ASKLENS = {"AUDIT_DATABASE_ALIAS": malformed_alias}
    api_client.force_authenticate(user=owner)

    response = api_client.get(f"/asklens/runs/{run.pk}/")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "asklens.execute.failed",
            "message": "The AskLens request could not be completed.",
        }
    }
    if malformed_alias:
        assert str(malformed_alias) not in response.content.decode()


@pytest.mark.django_db(transaction=True, databases=["default", "asklens_read"])
def test_invalid_audit_alias_fails_safely_without_default_fallback(
    settings,
    api_client: APIClient,
    owner,
    registered_orders: None,
) -> None:
    """Invalid server configuration neither reflects detail nor falls back."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "database",
        "AUDIT_DATABASE_ALIAS": "missing_synthetic_alias",
    }
    api_client.force_authenticate(user=owner)

    query = api_client.post(
        "/asklens/query/",
        {"question": QUESTION, "plan": aggregate_plan()},
        format="json",
    )

    assert query.status_code == 200
    assert "run_id" not in query.data
    assert SemanticQueryRun.objects.using("default").count() == 0
    assert "missing_synthetic_alias" not in json.dumps(query.data)

    default_run = SemanticQueryRun.objects.using("default").create(
        user=owner,
        question="",
        plan={},
        status=SemanticQueryRun.Status.SUCCESS,
    )
    detail = api_client.get(f"/asklens/runs/{default_run.pk}/")

    assert detail.status_code == 503
    assert detail.json() == {
        "error": {
            "code": "asklens.execute.failed",
            "message": "The AskLens request could not be completed.",
        }
    }
    assert "missing_synthetic_alias" not in detail.content.decode()
