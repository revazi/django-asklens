"""Executable checks for the narrow 0.3.x compatibility boundary."""

import inspect
from pathlib import Path

import django_asklens
import django_asklens.catalog as catalog
import django_asklens.execution as execution
import django_asklens.observability as observability
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.settings import DEFAULTS

ROOT = Path(__file__).resolve().parents[1]


def test_governed_core_imports_and_facade_signature_are_exact() -> None:
    for name in (
        "Metric",
        "SemanticResource",
        "register",
        "get_resource",
    ):
        assert getattr(django_asklens, name) is getattr(catalog, name)
    for name in (
        "CatalogRegistry",
        "Metric",
        "SemanticResource",
        "default_registry",
        "register",
        "get_resource",
    ):
        assert hasattr(catalog, name)

    assert execution.__all__ == ["QueryResult", "execute_plan"]
    signature = inspect.signature(execution.execute_plan)
    assert tuple(signature.parameters) == ("plan", "request", "registry")
    assert signature.parameters["plan"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert signature.parameters["request"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["registry"].kind is inspect.Parameter.KEYWORD_ONLY


def test_governed_observability_import_and_default_are_exact() -> None:
    assert observability.__all__ == ["ObservabilityEvent"]
    assert DEFAULTS["OBSERVABILITY_SINK"] is None
    assert not hasattr(django_asklens, "ObservabilityEvent")


def test_public_error_surface_remains_importable() -> None:
    assert issubclass(PublicAskLensError, Exception)
    assert callable(public_error_payload)


def test_policy_names_every_surface_tier_without_versioning_documents() -> None:
    policy = (ROOT / "docs" / "compatibility.md").read_text(encoding="utf-8")
    for required in (
        "# 0.3.x compatibility boundary",
        "## Exact surface table",
        "Registration and resources",
        "Trusted execution",
        "Public failures",
        "Host observability",
        "HTTP/DRF",
        "MCP",
        "Admin/frontend",
        "Five JSON documents and schemas",
        "Compiler, ORM bindings, private helpers",
        "## Change rules within 0.3.x",
        "## Upgrade from 0.2.x to 0.3.0",
        "not a 1.0 stability claim",
        "no migration",
        "previously validated plan",
        "no fixed deprecation period",
    ):
        assert required in policy
    assert "document version field" not in policy.lower()
    assert "schema negotiation" in policy
