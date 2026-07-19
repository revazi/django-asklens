"""Import-boundary tests for optional framework integrations."""

import os
import subprocess
import sys


def assert_import_does_not_import_drf(module_name: str) -> None:
    """Import one module in a fresh process and assert it did not import DRF."""

    code = f"""
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
    DATABASES={{
        "default": {{"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    }},
    USE_TZ=True,
)

import django

django.setup()

import sys
import {module_name}

imported = sorted(
    module_name
    for module_name in sys.modules
    if module_name == "rest_framework" or module_name.startswith("rest_framework.")
)
if imported:
    raise SystemExit("Imported DRF modules: " + ", ".join(imported))
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


def test_core_access_import_does_not_import_drf() -> None:
    """Core access helpers should be independent of DRF imports."""

    assert_import_does_not_import_drf("django_asklens.access")


def test_core_permissions_import_does_not_import_drf() -> None:
    """Request permission helpers should be independent of DRF imports."""

    assert_import_does_not_import_drf("django_asklens.permissions")


def test_core_querying_import_does_not_import_drf() -> None:
    """Shared query orchestration should be independent of DRF imports."""

    assert_import_does_not_import_drf("django_asklens.querying")


def test_mcp_adapter_import_does_not_import_drf() -> None:
    """Framework-neutral MCP helpers should be independent of DRF imports."""

    assert_import_does_not_import_drf("django_asklens.mcp")


def test_admin_import_does_not_import_drf() -> None:
    """Admin query helpers should not import DRF modules at import time."""

    assert_import_does_not_import_drf("django_asklens.admin")
