"""Read-only accessors for packaged draft internal contract schemas."""

import json
from importlib.resources import files
from typing import Any, Literal, cast

from django_asklens.contracts._generation import CONTRACT_SCHEMA_NAMES

type ContractSchemaName = Literal[
    "catalog",
    "query-plan",
    "capabilities",
    "result",
    "error",
]


def list_contract_schemas() -> tuple[str, ...]:
    """Return the exact one-current-shape internal schema name set."""

    return CONTRACT_SCHEMA_NAMES


def get_contract_schema(name: ContractSchemaName) -> dict[str, Any]:
    """Return a fresh mapping loaded from one packaged internal JSON Schema."""

    if name not in CONTRACT_SCHEMA_NAMES:
        msg = f"Unknown AskLens contract schema {name!r}."
        raise ValueError(msg)
    schema_path = files("django_asklens.contracts").joinpath(
        "schemas", f"{name}.schema.json"
    )
    return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))
