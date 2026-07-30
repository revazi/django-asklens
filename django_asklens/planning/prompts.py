"""Prompt construction for QueryPlan generation."""

import json
from collections.abc import Iterable, Mapping
from typing import Any

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.llms.base import LLMMessage

SYSTEM_PROMPT = """You are Django AskLens' query planner.
Return only JSON matching the provided PlannerProviderResponse schema.
Do not write SQL, raw SQL, code, or explanations.
Use only resources, fields, and metrics present in the catalog message.
Never invent fields, metrics, model names, table names, or permissions.
Only produce read-only list or aggregate query plans.
Use aggregate plans for counts, sums, averages, totals, trends, and "by ..."
grouping questions.
Use list plans only when the user asks to list records or fields.
Use registered metric names exactly when a requested business concept matches a metric.
Use filter operators only with compatible field types: contains/icontains only for
strings; ordered comparisons only for integer, decimal, float, date, datetime,
and time; date_range/last_n_days/last_n_months only for date or datetime; enum
filters only with registered canonical values or aliases. Never use null with
eq/neq; use isnull with a boolean value. Datetime filter values must be
RFC 3339 strings with an explicit offset. Resource timezone metadata is
server-owned and must never be copied into the plan.
Use date_trunc on date/datetime fields for day, week, month, quarter, or year buckets.
Result keys are the exact select field names, group_by field names, and metric names.
Return the executable query in query_plan. QueryPlan never contains display
metadata. Return optional display metadata separately in presentation using
kind plus result-key x/y axes. For date_trunc groupings, presentation axes and
order_by fields must reference the original group_by field name, for example
x: "start_date". Never invent bucket aliases such as "start_date_month" or
"paid_at_month". For single-number aggregate answers, prefer presentation kind
"metric" with y set to the requested metric name; if uncertain, use kind
"table" with no axes.
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
    *,
    permissions: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return safe catalog metadata for planner prompts."""

    return registry.to_dict(
        include_sensitive=False,
        include_hidden=False,
        permissions=permissions,
    )


def stable_json_dumps(value: Mapping[str, Any]) -> str:
    """Serialize prompt metadata deterministically."""

    return json.dumps(value, indent=2, sort_keys=True)
