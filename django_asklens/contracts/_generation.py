"""Generate and validate the one current set of internal contract schemas."""

import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, cast

from pydantic import BaseModel

from django_asklens.contracts._models import (
    CapabilitiesDocument,
    CatalogDocument,
    ErrorDocument,
    ResultDocument,
)
from django_asklens.planning.schemas import QueryPlan

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
CONTRACT_SCHEMA_NAMES = (
    "catalog",
    "query-plan",
    "capabilities",
    "result",
    "error",
)

_SCHEMA_MODELS: Mapping[str, type[BaseModel]] = {
    "catalog": CatalogDocument,
    "query-plan": QueryPlan,
    "capabilities": CapabilitiesDocument,
    "result": ResultDocument,
    "error": ErrorDocument,
}
_SCHEMA_TITLES = {
    "catalog": "AskLens Internal Catalog",
    "query-plan": "AskLens Internal QueryPlan",
    "capabilities": "AskLens Internal Capabilities",
    "result": "AskLens Internal Result",
    "error": "AskLens Internal Error",
}


def _tighten_query_plan_schema(schema: dict[str, Any]) -> None:
    """Represent structural validators that Pydantic cannot emit automatically."""

    definitions = schema["$defs"]
    properties = schema["properties"]
    properties["resource"]["minLength"] = 1
    properties["select"]["items"]["minLength"] = 1
    properties["limit"]["minimum"] = 1
    for definition_name in ("FilterSpec", "GroupBySpec", "MetricSpec"):
        member_name = "metric" if definition_name == "MetricSpec" else "field"
        definitions[definition_name]["properties"][member_name]["minLength"] = 1

    definitions["OrderBySpec"]["oneOf"] = [
        {
            "properties": {
                "field": {"minLength": 1, "type": "string"},
                "metric": {"type": "null"},
            },
            "required": ["field"],
        },
        {
            "properties": {
                "field": {"type": "null"},
                "metric": {"minLength": 1, "type": "string"},
            },
            "required": ["metric"],
        },
    ]
    definitions["FilterSpec"]["allOf"] = [
        {
            "if": {
                "properties": {"op": {"const": "isnull"}},
                "required": ["op"],
            },
            "then": {"properties": {"value": {"type": "boolean"}}},
        },
        {
            "if": {
                "properties": {"op": {"const": "in"}},
                "required": ["op"],
            },
            "then": {
                "properties": {
                    "value": {
                        "items": {"$ref": "#/$defs/JsonScalar"},
                        "minItems": 1,
                        "type": "array",
                    }
                }
            },
        },
        {
            "if": {
                "properties": {"op": {"const": "date_range"}},
                "required": ["op"],
            },
            "then": {
                "properties": {
                    "value": {
                        "items": {"minLength": 1, "type": "string"},
                        "maxItems": 2,
                        "minItems": 2,
                        "type": "array",
                    }
                }
            },
        },
        {
            "if": {
                "properties": {"op": {"enum": ["last_n_days", "last_n_months"]}},
                "required": ["op"],
            },
            "then": {"properties": {"value": {"minimum": 1, "type": "integer"}}},
        },
        {
            "if": {
                "properties": {
                    "op": {
                        "enum": [
                            "eq",
                            "neq",
                            "contains",
                            "icontains",
                            "gt",
                            "gte",
                            "lt",
                            "lte",
                        ]
                    }
                },
                "required": ["op"],
            },
            "then": {"properties": {"value": {"$ref": "#/$defs/JsonScalar"}}},
        },
    ]


def _tighten_result_schema(schema: dict[str, Any]) -> None:
    """Constrain dynamic row-map keys while retaining their approved shape."""

    row_schema = schema["properties"]["data"]["items"]
    row_schema["propertyNames"] = {"minLength": 1}


def _strip_generation_defaults(value: object) -> None:
    """Remove model defaults that are not serialized document members."""

    if isinstance(value, dict):
        value.pop("default", None)
        for child in value.values():
            _strip_generation_defaults(child)
    elif isinstance(value, list):
        for child in value:
            _strip_generation_defaults(child)


def build_contract_schema(name: str) -> dict[str, Any]:
    """Build one deterministic Draft 2020-12 internal schema."""

    try:
        model = _SCHEMA_MODELS[name]
    except KeyError as exc:
        msg = f"Unknown AskLens contract schema {name!r}."
        raise ValueError(msg) from exc
    schema = deepcopy(model.model_json_schema())
    if name == "query-plan":
        _tighten_query_plan_schema(schema)
    elif name == "result":
        _tighten_result_schema(schema)
    _strip_generation_defaults(schema)
    schema["$schema"] = DRAFT_2020_12
    schema["$id"] = f"{name}.schema.json"
    schema["title"] = _SCHEMA_TITLES[name]
    return cast(dict[str, Any], schema)


def validate_contract_document(name: str, document: Mapping[str, Any]) -> None:
    """Validate a runtime example against the model that generates its schema."""

    try:
        model = _SCHEMA_MODELS[name]
    except KeyError as exc:
        msg = f"Unknown AskLens contract schema {name!r}."
        raise ValueError(msg) from exc
    model.model_validate_json(json.dumps(document), strict=True)
