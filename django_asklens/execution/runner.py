"""Execute untrusted AskLens plans through the trusted facade."""

import warnings
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from time import perf_counter
from typing import Any, Never

from django.core.exceptions import FieldError
from django.utils import timezone

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.compiler import ResultColumn
from django_asklens.compiler.orm import (
    LimitScope,
    _compile_prepared_query,
    _CompiledQuery,
    _PreparedQueryPlan,
)
from django_asklens.exceptions import (
    AskLensError,
    AuthorizationDeniedError,
    BindingInvalidError,
    CompilationError,
    ExecutionError,
    PlanValidationError,
    PublicAskLensError,
    ScopeUnavailableError,
    normalize_public_error,
)
from django_asklens.execution.audit import (
    _AuditPolicy,
    _AuditSink,
    _build_audit_event,
    _emit_audit_event,
    _resolve_audit_policy_and_sink,
)
from django_asklens.permissions import get_request_permissions
from django_asklens.planning.schemas import QueryPlan
from django_asklens.planning.validation import parse_and_validate_query_plan
from django_asklens.results import serialize_query_result, serialize_rows

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
    audit_policy: _AuditPolicy
    audit_sink: _AuditSink | None

    def __reduce__(self) -> Never:
        """Prevent current request state from being serialized or reused."""

        msg = "AskLens execution context is short-lived and not serializable."
        raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Normalized result produced by executing a compiled query."""

    columns: tuple[ResultColumn, ...]
    rows: tuple[dict[str, Any], ...]
    row_count: int
    duration_ms: int
    visualization: dict[str, Any]
    limit: int
    limit_scope: LimitScope
    truncated: bool
    _validated_plan: QueryPlan | None = field(default=None, repr=False, compare=False)
    _audit_record: Any = field(default=None, repr=False, compare=False)

    def to_dict(self, *, include_visualization: bool = True) -> dict[str, Any]:
        """Serialize the result to JSON-safe primitives plus optional hints."""

        serialized = serialize_query_result(
            columns=self.columns,
            rows=self.rows,
            visualization=self.visualization,
            include_visualization=include_visualization,
        )
        return {
            **serialized,
            "duration_ms": self.duration_ms,
            "result_metadata": {
                "limit": self.limit,
                "limit_scope": self.limit_scope,
                "truncated": self.truncated,
            },
        }


def execute_plan(
    plan: UntrustedPlan,
    *,
    request: Any,
    registry: CatalogRegistry = default_registry,
) -> QueryResult:
    """Revalidate and execute an untrusted plan for the current request."""

    context = _build_public_execution_context(
        request=request,
        registry=registry,
        now=None,
        require_request=True,
    )
    return _execute_public_plan(plan, context=context)


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
    context = _build_public_execution_context(
        request=request,
        registry=registry,
        now=now,
        require_request=True,
    )
    return _execute_public_plan(plan, context=context)


def _build_public_execution_context(
    *,
    request: Any,
    registry: CatalogRegistry,
    now: datetime | None,
    require_request: bool,
) -> _ExecutionContext:
    """Build current context while exposing only a normalized safe error."""

    try:
        return _build_execution_context(
            request=request,
            registry=registry,
            now=now,
            require_request=require_request,
        )
    except PublicAskLensError:
        raise
    except AskLensError as exc:
        raise normalize_public_error(exc) from None


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
        raise AuthorizationDeniedError(msg)

    resolved_now = now or timezone.now()
    if timezone.is_naive(resolved_now):
        msg = "AskLens execution requires an aware request clock."
        raise PlanValidationError(msg)

    try:
        permissions = get_request_permissions(request)
    except Exception as exc:
        msg = "AskLens could not resolve current request permissions."
        raise AuthorizationDeniedError(msg) from exc

    audit_policy, audit_sink = _resolve_audit_policy_and_sink(request=request)
    return _ExecutionContext(
        request=request,
        principal=getattr(request, "user", None),
        permissions=permissions,
        registry=registry,
        registry_revision=tuple(
            (resource.name, id(resource)) for resource in registry.all()
        ),
        now=resolved_now,
        audit_policy=audit_policy,
        audit_sink=audit_sink,
    )


def _execute_public_plan(
    plan: UntrustedPlan,
    *,
    context: _ExecutionContext,
) -> QueryResult:
    """Execute and audit while exposing only safe public error metadata."""

    validated_plan: QueryPlan | None = None
    try:
        validated_plan = _validate_untrusted_plan(plan, context=context)
        result = _execute_validated_plan(validated_plan, context=context)
    except AskLensError as exc:
        public_error = normalize_public_error(exc)
        audit_record = _audit_execution(
            context=context,
            validated_plan=validated_plan,
            result=None,
            error=public_error,
        )
        public_error._audit_record = audit_record
        public_error._audit_attempted = True
        raise public_error from None

    audit_record = _audit_execution(
        context=context,
        validated_plan=validated_plan,
        result=result,
        error=None,
    )
    return replace(
        result,
        _validated_plan=validated_plan,
        _audit_record=audit_record,
    )


def _validate_untrusted_plan(
    plan: UntrustedPlan,
    *,
    context: _ExecutionContext,
) -> QueryPlan:
    """Reparse and validate ordinary plan input for the current context."""

    raw_plan: str | bytes | Mapping[str, Any]
    if isinstance(plan, QueryPlan):
        raw_plan = plan.model_dump(mode="json", exclude_unset=True)
    else:
        raw_plan = plan

    return parse_and_validate_query_plan(
        raw_plan,
        registry=context.registry,
        permissions=context.permissions,
    )


def _execute_validated_plan(
    validated_plan: QueryPlan,
    *,
    context: _ExecutionContext,
) -> QueryResult:
    """Prepare, compile, and execute one currently validated plan."""

    prepared = _prepare_query_plan(validated_plan, context=context)
    try:
        compiled_query = _compile_prepared_query(prepared)
    except AskLensError:
        raise
    except (FieldError, KeyError) as exc:
        msg = "AskLens could not resolve a private query binding."
        raise BindingInvalidError(msg) from exc
    except Exception as exc:
        msg = "AskLens could not compile the prepared query."
        raise CompilationError(msg) from exc

    try:
        return _execute_compiled_query(compiled_query, context=context)
    except AskLensError:
        raise
    except Exception as exc:
        msg = "AskLens could not evaluate the compiled query."
        raise ExecutionError(msg) from exc


def _audit_execution(
    *,
    context: _ExecutionContext,
    validated_plan: QueryPlan | None,
    result: QueryResult | None,
    error: AskLensError | None,
) -> Any:
    """Emit one privacy-aware event for a success or safe rejection."""

    plan_payload = (
        validated_plan.model_dump(mode="json") if validated_plan is not None else None
    )
    event = _build_audit_event(
        policy=context.audit_policy,
        timestamp=context.now,
        principal=context.principal,
        resource=validated_plan.resource if validated_plan is not None else None,
        intent=validated_plan.intent if validated_plan is not None else None,
        status="failed" if error is not None else "success",
        row_count=result.row_count if result is not None else 0,
        duration_ms=result.duration_ms if result is not None else None,
        error=error,
        validated_plan=plan_payload,
    )
    return _emit_audit_event(sink=context.audit_sink, event=event)


def _prepare_query_plan(
    plan: QueryPlan,
    *,
    context: _ExecutionContext,
) -> _PreparedQueryPlan:
    """Bind a validated plan to current resource scope and request state."""

    resource = context.registry.get(plan.resource)
    try:
        queryset = resource.get_scope_queryset(context.request)
    except AskLensError:
        raise
    except Exception as exc:
        msg = "AskLens could not resolve the current resource scope."
        raise ScopeUnavailableError(msg) from exc

    return _PreparedQueryPlan(
        plan=plan,
        resource=resource,
        queryset=queryset,
        now=context.now,
        context_binding=context,
    )


def _execute_compiled_query(
    compiled_query: _CompiledQuery,
    *,
    context: _ExecutionContext,
) -> QueryResult:
    """Evaluate only a private query bound to this execution context."""

    if not isinstance(compiled_query, _CompiledQuery):
        msg = "AskLens executor requires an internal compiled query."
        raise TypeError(msg)
    if compiled_query.context_binding is not context:
        msg = "AskLens compiled query is not bound to the current execution context."
        raise TypeError(msg)

    started = perf_counter()
    if compiled_query.aggregate_expressions is None:
        raw_rows = compiled_query.queryset
    else:
        raw_rows = (
            compiled_query.queryset.aggregate(**compiled_query.aggregate_expressions),
        )
    fetched_rows = tuple(
        normalize_row(row, key_map=compiled_query.key_map) for row in raw_rows
    )
    duration_ms = round((perf_counter() - started) * 1000)
    truncated = (
        compiled_query.detects_truncation and len(fetched_rows) > compiled_query.limit
    )
    rows = fetched_rows[: compiled_query.limit]

    result = QueryResult(
        columns=compiled_query.columns,
        rows=rows,
        row_count=len(rows),
        duration_ms=duration_ms,
        visualization=compiled_query.visualization,
        limit=compiled_query.limit,
        limit_scope=compiled_query.limit_scope,
        truncated=truncated,
    )
    # Serialization is part of trusted execution: unsupported runtime objects
    # fail before a successful result is returned or audited.
    serialize_rows(columns=result.columns, rows=result.rows)
    return result


def normalize_row(
    row: Mapping[str, Any], *, key_map: Mapping[str, str]
) -> dict[str, Any]:
    """Normalize ORM values-row keys back to public catalog keys."""

    return {key_map.get(key, key): value for key, value in row.items()}
