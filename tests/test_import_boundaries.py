"""Import-boundary tests for optional framework integrations."""

import os
import subprocess
import sys

import pytest


def assert_import_does_not_import_optional_packages(module_name: str) -> None:
    """Import one source surface without loading DRF or FastMCP."""

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

optional_packages = ("rest_framework", "fastmcp")
imported = sorted(
    module_name
    for module_name in sys.modules
    if any(
        module_name == package_name or module_name.startswith(f"{{package_name}}.")
        for package_name in optional_packages
    )
)
if imported:
    raise SystemExit("Imported optional modules: " + ", ".join(imported))
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


@pytest.mark.parametrize(
    "module_name",
    (
        "django_asklens",
        "django_asklens.access",
        "django_asklens.permissions",
        "django_asklens.querying",
        "django_asklens.admin_querying",
        "django_asklens.admin",
        "django_asklens.mcp",
        "django_asklens.mcp.core",
        "django_asklens.mcp.wrappers",
    ),
)
def test_core_surface_does_not_import_optional_packages(module_name: str) -> None:
    """Root, shared, admin, and dependency-free MCP imports remain core-only."""

    assert_import_does_not_import_optional_packages(module_name)
