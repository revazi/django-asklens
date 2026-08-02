"""Django AskLens package."""

from django_asklens.catalog import (
    Metric,
    SemanticResource,
    build_capabilities,
    get_resource,
    register,
    serialize_catalog,
)
from django_asklens.contracts import (
    CONTRACT_SCHEMA_NAMES,
    get_contract_schema,
    list_contract_schemas,
)

__version__ = "0.1.0a1"

__all__ = [
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
