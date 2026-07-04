"""Execute compiled AskLens ORM queries."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.compiler import CompiledQuery, ResultColumn, compile_query_plan
from django_asklens.planning.schemas import QueryPlan
from django_asklens.renderers import render_query_result


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Normalized result produced by executing a compiled query."""

    columns: tuple[ResultColumn, ...]
    rows: tuple[dict[str, Any], ...]
    row_count: int
    duration_ms: int
    visualization: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result to table/chart-ready primitives."""

        rendered = render_query_result(
            columns=self.columns,
            rows=self.rows,
            visualization=self.visualization,
        )
        return {**rendered, "duration_ms": self.duration_ms}


def run_query_plan(
    plan: QueryPlan,
    *,
    registry: CatalogRegistry = default_registry,
    request: Any = None,
    now: datetime | None = None,
) -> QueryResult:
    """Compile and execute a validated QueryPlan."""

    return execute_query(
        compile_query_plan(plan, registry=registry, request=request, now=now)
    )


def execute_query(compiled_query: CompiledQuery) -> QueryResult:
    """Execute a compiled ORM query and normalize row keys."""

    started = perf_counter()
    rows = tuple(
        normalize_row(row, key_map=compiled_query.key_map)
        for row in compiled_query.queryset
    )
    duration_ms = round((perf_counter() - started) * 1000)

    return QueryResult(
        columns=compiled_query.columns,
        rows=rows,
        row_count=len(rows),
        duration_ms=duration_ms,
        visualization=compiled_query.visualization,
    )


def normalize_row(
    row: Mapping[str, Any], *, key_map: Mapping[str, str]
) -> dict[str, Any]:
    """Normalize ORM values-row keys back to public catalog keys."""

    return {key_map.get(key, key): value for key, value in row.items()}
