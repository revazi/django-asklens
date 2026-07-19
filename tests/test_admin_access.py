"""Tests for AskLens admin access gates."""

import os
import subprocess
import sys


def test_admin_query_gate_uses_configured_asklens_permission_classes() -> None:
    """The admin query POST gate should honor the shared AskLens route gate."""

    code = """
from types import SimpleNamespace

from django.conf import settings

settings.configure(
    SECRET_KEY="test",
    INSTALLED_APPS=[
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.admin",
        "django_asklens",
    ],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    DJANGO_ASKLENS={
        "API_PERMISSION_CLASSES": [
            "tests.test_project.permissions.DenyAskLensAccess",
        ],
    },
    USE_TZ=True,
)

import django

django.setup()

from django.test import RequestFactory

from django_asklens.admin import can_query_asklens_from_admin

request = RequestFactory().post("/admin/asklens/asklensquery/")
request.user = SimpleNamespace(is_authenticated=True, is_staff=True)

if can_query_asklens_from_admin(request) is not False:
    raise SystemExit("Admin query gate did not honor DenyAskLensAccess")
"""
    env = dict(os.environ)
    env.pop("DJANGO_SETTINGS_MODULE", None)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
