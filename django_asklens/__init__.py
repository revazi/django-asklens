"""Django AskLens package."""

from django_asklens.catalog import (
    Metric,
    SemanticResource,
    build_capabilities,
    get_resource,
    register,
    serialize_catalog,
)

__version__ = "0.1.0a0"

__all__ = [
    "Metric",
    "SemanticResource",
    "__version__",
    "build_capabilities",
    "get_resource",
    "register",
    "serialize_catalog",
]
