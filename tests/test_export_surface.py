"""Regression coverage for the supported Python export surface."""

from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

import django_asklens
import django_asklens.querying as querying
from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from tests.test_project.models import Order

ROOT_EXPORTS = [
    "CONTRACT_SCHEMA_NAMES",
    "Metric",
    "SemanticResource",
    "__version__",
    "build_capabilities",
    "get_contract_schema",
    "get_resource",
    "list_contract_schemas",
    "register",
    "serialize_catalog",
]
QUERYING_EXPORTS = [
    "AskLensQueryResponse",
    "execute_asklens_query_request",
]
VIEW_EXPORTS = [
    "AskLensAPIView",
    "CapabilitiesView",
    "CatalogView",
    "QueryRunDetailView",
    "QueryView",
]
REMOVED_QUERYING_HELPERS = (
    "QueryResponseType",
    "build_capabilities_payload",
    "build_presentation_payload",
    "build_result_metadata",
    "build_success_payload",
    "enforce_debug_permission",
    "get_query_help_for_capabilities",
    "get_user_permissions",
    "safe_error_category",
    "safe_error_message",
    "safe_error_payload",
    "safe_provider_fallback_message",
    "should_return_capabilities_fallback",
    "should_use_unified_provider_response",
)
REMOVED_VIEW_HELPERS = (
    "build_capabilities_payload",
    "build_success_payload",
    "can_view_run",
    "enforce_debug_permission",
    "get_query_help_for_capabilities",
    "get_user_permissions",
    "safe_error_message",
    "should_return_capabilities_fallback",
    "should_use_unified_provider_response",
)


def _direct_import(module_name: str, symbol: str) -> None:
    namespace: dict[str, object] = {}
    exec(f"from {module_name} import {symbol}", namespace)  # noqa: S102


def test_exact_supported_exports() -> None:
    """Pin deliberate root, orchestration, and optional-view exports."""

    from django_asklens.api import views

    assert django_asklens.__all__ == ROOT_EXPORTS
    assert querying.__all__ == QUERYING_EXPORTS
    assert views.__all__ == VIEW_EXPORTS


@pytest.mark.parametrize("helper", REMOVED_QUERYING_HELPERS)
def test_querying_helpers_are_not_directly_importable(helper: str) -> None:
    """Internal orchestration steps must not remain accidental attributes."""

    with pytest.raises(ImportError):
        _direct_import("django_asklens.querying", helper)
    assert not hasattr(querying, helper)


@pytest.mark.parametrize("helper", REMOVED_VIEW_HELPERS)
def test_view_implementation_helpers_are_not_directly_importable(helper: str) -> None:
    """The view module exports and exposes view classes only."""

    from django_asklens.api import views

    with pytest.raises(ImportError):
        _direct_import("django_asklens.api.views", helper)
    assert not hasattr(views, helper)


def test_deprecated_api_querying_module_is_absent() -> None:
    """The removed DRF-era compatibility module has no import fallback or file."""

    with pytest.raises(ModuleNotFoundError) as caught:
        importlib.import_module("django_asklens.api.querying")
    assert caught.value.name == "django_asklens.api.querying"
    assert "django_asklens.api.querying" not in sys.modules
    assert importlib.util.find_spec("django_asklens.api.querying") is None

    api_spec = importlib.util.find_spec("django_asklens.api")
    assert api_spec is not None
    assert api_spec.submodule_search_locations is not None
    api_directory = Path(next(iter(api_spec.submodule_search_locations)))
    assert not (api_directory / "querying.py").exists()


def test_core_export_imports_remain_drf_free() -> None:
    """Importing the root and canonical orchestrator must not require DRF."""

    code = r"""
import importlib.abc
import sys


class BlockRestFramework(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "rest_framework" or fullname.startswith("rest_framework."):
            raise ModuleNotFoundError("rest_framework is intentionally blocked")
        return None


sys.meta_path.insert(0, BlockRestFramework())

from django.conf import settings

settings.configure(
    SECRET_KEY="export-surface-test",
    INSTALLED_APPS=[
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django_asklens",
    ],
    DATABASES={
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    },
    USE_TZ=True,
)

import django

django.setup()

import django_asklens
import django_asklens.querying

assert "rest_framework" not in sys.modules
assert django_asklens.querying.__all__ == [
    "AskLensQueryResponse",
    "execute_asklens_query_request",
]
"""
    env = dict(os.environ)
    env.pop("DJANGO_SETTINGS_MODULE", None)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", textwrap.dedent(code)],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.django_db
def test_public_orchestrator_still_executes_through_the_trusted_path(settings) -> None:
    """The retained question orchestrator still executes an untrusted plan."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}
    default_registry.clear()
    try:
        default_registry.register(
            model=Order,
            name="export_surface_orders",
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
                Metric(
                    "order_count",
                    op="count",
                    binding="id",
                    result_type="integer",
                )
            ],
        )
        request = SimpleNamespace(
            user=SimpleNamespace(
                is_authenticated=True,
                is_staff=False,
                get_all_permissions=lambda: set(),
            )
        )

        outcome = querying.execute_asklens_query_request(
            request,
            question="List synthetic export-surface orders",
            provided_plan={
                "resource": "export_surface_orders",
                "intent": "list",
                "select": ["id"],
                "limit": 10,
            },
        )

        assert isinstance(outcome, querying.AskLensQueryResponse)
        assert outcome.response_type == "query"
        assert outcome.status_code == 200
        assert outcome.payload["plan"]["resource"] == "export_surface_orders"
        assert outcome.payload["data"] == []
        assert outcome.run is None
    finally:
        default_registry.clear()
