"""Prompt construction for QueryPlan generation."""

import json
from collections.abc import Mapping
from typing import Any

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.llms.base import LLMMessage

SYSTEM_PROMPT = """You are Django AskLens' query planner.
Return only JSON matching the provided QueryPlan schema.
Do not write SQL, raw SQL, code, or explanations.
Use only resources, fields, and metrics present in the catalog message.
Never invent fields, metrics, model names, table names, or permissions.
Only produce read-only list or aggregate query plans.
If a question asks for data outside the catalog, choose the safest valid plan
or fail via validation by not inventing fields.
""".strip()


def build_planner_messages(
    *,
    question: str,
    catalog: Mapping[str, Any],
) -> tuple[LLMMessage, ...]:
    """Build provider messages for strict QueryPlan generation."""

    return (
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
        {
            "role": "user",
            "content": "Catalog metadata:\n" + stable_json_dumps(catalog),
        },
    )


def build_planner_catalog(
    registry: CatalogRegistry = default_registry,
) -> dict[str, Any]:
    """Return safe catalog metadata for planner prompts."""

    return registry.to_dict(
        include_sensitive=False,
        include_hidden=False,
        include_internal=False,
    )


def stable_json_dumps(value: Mapping[str, Any]) -> str:
    """Serialize prompt metadata deterministically."""

    return json.dumps(value, indent=2, sort_keys=True)
