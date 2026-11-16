"""Shared synthetic test fixtures, never an authentication backend or seed policy."""

import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from django_asklens.models import SemanticQueryRun

PAID_QUESTION = "Show my paid orders"
EMPTY_QUESTION = "Show my refunded orders"
ALICE_ROWS = [
    {"product": "North class", "total_cents": 2000},
    {"product": "North membership", "total_cents": 1200},
]


def seed():
    call_command("seed_quickstart", stdout=StringIO())


def permission(codename="view_order", app="shop"):
    return Permission.objects.get(content_type__app_label=app, codename=codename)


def sign_in(client, username="asklens-alice", url="/accounts/login/"):
    """Real session login + CSRF, with a test-only password never seeded by default."""
    user = get_user_model().objects.get(username=username)
    password = "synthetic-recipe-test-only"
    user.set_password(password)
    user.save()
    response = client.get(url)
    assert response.status_code == 200
    token = client.cookies["csrftoken"].value
    response = client.post(
        url,
        {"username": username, "password": password, "csrfmiddlewaretoken": token},
    )
    assert response.status_code == 302
    return user


def csrf_post(client, url, data, *, api=False):
    token = client.cookies["csrftoken"].value
    if api:
        return client.post(
            url,
            json.dumps(data),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
    return client.post(url, {**data, "csrfmiddlewaretoken": token})


def assert_no_order_sql(callback):
    with CaptureQueriesContext(connection) as queries:
        result = callback()
    assert not any('"shop_order"' in query["sql"] for query in queries)
    return result


def assert_metadata_audit():
    for run in SemanticQueryRun.objects.all():
        assert run.question == ""
        assert not set(run.plan) - {"resource", "intent"}
        assert "shop.view_order" not in str(run.plan)
