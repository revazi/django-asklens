"""Regression tests for private compiler and executor boundaries."""

import pickle

import pytest

import django_asklens.compiler as compiler_package
import django_asklens.execution as execution_package
from django_asklens.compiler.orm import _compile_prepared_query
from django_asklens.execution.runner import (
    _build_execution_context,
    _execute_compiled_query,
    _prepare_query_plan,
)
from tests.execution.test_facade import build_registry, request_with, status_plan

pytestmark = pytest.mark.django_db


def test_unchecked_compiler_and_executor_are_not_public_exports() -> None:
    """Public packages must not expose operations that bypass the facade."""

    assert "compile_query_plan" not in compiler_package.__all__
    assert not hasattr(compiler_package, "compile_query_plan")
    assert "CompiledQuery" not in compiler_package.__all__
    assert not hasattr(compiler_package, "CompiledQuery")
    assert "execute_query" not in execution_package.__all__
    assert not hasattr(execution_package, "execute_query")


def test_internal_compiler_rejects_an_ordinary_query_plan() -> None:
    """Shape-valid plans are not accepted by the private compiler boundary."""

    with pytest.raises(TypeError, match="prepared query plan"):
        _compile_prepared_query(status_plan())  # type: ignore[arg-type]


def test_internal_executor_rejects_an_arbitrary_object() -> None:
    """Only the private compiled-query representation reaches evaluation."""

    with pytest.raises(TypeError, match="compiled query"):
        _execute_compiled_query(
            object(),  # type: ignore[arg-type]
            context=object(),  # type: ignore[arg-type]
        )


def test_prepared_state_is_context_bound_lazy_and_not_serializable(
    django_assert_num_queries,
) -> None:
    """Prepared state stays short-lived and compilation performs no SQL."""

    registry = build_registry()
    request = request_with("shop.view_orders")

    with django_assert_num_queries(0):
        context = _build_execution_context(
            request=request,
            registry=registry,
            now=None,
            require_request=True,
        )
        prepared = _prepare_query_plan(
            status_plan(),
            context=context,
        )
        compiled = _compile_prepared_query(prepared)

    assert prepared.context_binding is context
    assert compiled.context_binding is context
    assert compiled.queryset is not None

    with django_assert_num_queries(0):
        other_context = _build_execution_context(
            request=request,
            registry=registry,
            now=None,
            require_request=True,
        )
        with pytest.raises(TypeError, match="current execution context"):
            _execute_compiled_query(compiled, context=other_context)

    for short_lived_state in (context, prepared, compiled):
        with pytest.raises(TypeError, match="short-lived"):
            pickle.dumps(short_lived_state)
