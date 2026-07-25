"""Execute untrusted AskLens plans through the trusted facade."""

import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any

from django.utils import timezone

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.compiler import CompiledQuery, ResultColumn, compile_query_plan
from django_asklens.exceptions import PlanValidationError
from django_asklens.permissions import get_request_permissions
from django_asklens.planning.schemas import QueryPlan
from django_asklens.planning.validation import parse_and_validate_query_plan
from django_asklens.results import serialize_query_result

type UntrustedPlan = str | bytes | Mapping[str, Any] | QueryPlan


@dataclass(frozen=True, slots=True)
class _ExecutionContext:
    """Internal current-request state used for one execution only."""

    request: Any
    principal: Any
    permissions: frozenset[str]
    registry: CatalogRegistry
    registry_revision: tuple[tuple[str, int], ...]
    now: datetime
    audit_policy: str
    audit_sink: Any


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Normalized result produced by executing a compiled query."""

    columns: tuple[ResultColumn, ...]
    rows: tuple[dict[str, Any], ...]
    row_count: int
    duration_ms: int
    visualization: dict[str, Any]

    def to_dict(self, *, include_visualization: bool = True) -> dict[str, Any]:
        """Serialize the result to JSON-safe primitives plus optional hints."""

        serialized = serialize_query_result(
            columns=self.columns,
            rows=self.rows,
            visualization=self.visualization,
            include_visualization=include_visualization,
        )
        return {**serialized, "duration_ms": self.duration_ms}


def execute_plan(
    plan: UntrustedPlan,
    *,
    request: Any,
    registry: CatalogRegistry = default_registry,
) -> QueryResult:
    """Revalidate and execute an untrusted plan for the current request."""

    context = _build_execution_context(
        request=request,
        registry=registry,
        now=None,
        require_request=True,
    )
    return _execute_untrusted_plan(plan, context=context)


def run_query_plan(
    plan: UntrustedPlan,
    *,
    registry: CatalogRegistry = default_registry,
    request: Any = None,
    now: datetime | None = None,
) -> QueryResult:
    """Deprecated compatibility wrapper that revalidates before execution."""

    warnings.warn(
        "run_query_plan() is deprecated; use execute_plan() with the current "
        "request instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    context = _build_execution_context(
        request=request,
        registry=registry,
        now=now,
        require_request=False,
    )
    return _execute_untrusted_plan(plan, context=context)


def _build_execution_context(
    *,
    request: Any,
    registry: CatalogRegistry,
    now: datetime | None,
    require_request: bool,
) -> _ExecutionContext:
    """Resolve immutable server-owned state for one execution."""

    if require_request and request is None:
        msg = "execute_plan() requires the current Django request."
        raise PlanValidationError(msg)

    resolved_now = now or timezone.now()
    if timezone.is_naive(resolved_now):
        msg = "AskLens execution requires an aware request clock."
        raise PlanValidationError(msg)

    return _ExecutionContext(
        request=request,
        principal=getattr(request, "user", None),
        permissions=get_request_permissions(request),
        registry=registry,
        registry_revision=tuple(
            (resource.name, id(resource)) for resource in registry.all()
        ),
        now=resolved_now,
        audit_policy="delegated_legacy_database",
        audit_sink=None,
    )


def _execute_untrusted_plan(
    plan: UntrustedPlan,
    *,
    context: _ExecutionContext,
) -> QueryResult:
    """Parse, revalidate, compile, and execute within one current context."""

    raw_plan: str | bytes | Mapping[str, Any]
    if isinstance(plan, QueryPlan):
        raw_plan = plan.model_dump(mode="json")
    else:
        raw_plan = plan

    validated_plan = parse_and_validate_query_plan(
        raw_plan,
        registry=context.registry,
        permissions=context.permissions,
    )
    compiled_query = compile_query_plan(
        validated_plan,
        registry=context.registry,
        request=context.request,
        now=context.now,
    )
    return execute_query(compiled_query)


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
