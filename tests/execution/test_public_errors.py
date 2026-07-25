"""Stable public-error tests for the trusted execution boundary."""

import traceback

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import (
    AuthorizationDeniedError,
    BindingInvalidError,
    BudgetExceededError,
    CompilationError,
    ExecutionError,
    LLMProviderError,
    PermissionDeniedError,
    PlanParseError,
    PlanValidationError,
    PublicAskLensError,
    ScopeUnavailableError,
    public_error_payload,
)
from django_asklens.execution import execute_plan
from django_asklens.planning import parse_query_plan
from tests.execution.test_facade import (
    build_registry,
    request_with,
    sensitive_plan,
    status_plan,
)
from tests.test_project.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def disable_audit(settings) -> None:
    """Keep public-error stage tests in zero-total-SQL audit mode."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}


MEMBER_ERROR = {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable.",
}


def capture_public_error(call) -> PublicAskLensError:
    """Run a callable and return its normalized public exception."""

    with pytest.raises(PublicAskLensError) as caught:
        call()
    return caught.value


def test_unknown_and_unauthorized_members_have_identical_public_errors(
    django_assert_num_queries,
) -> None:
    """Member opacity must hold for direct Python execution before SQL."""

    unknown_plan = parse_query_plan(
        {
            "resource": "orders",
            "intent": "list",
            "select": ["missing.private_field"],
            "limit": 10,
        }
    )
    registry = build_registry()
    request = request_with("shop.view_orders")

    with django_assert_num_queries(0):
        unknown = capture_public_error(
            lambda: execute_plan(unknown_plan, request=request, registry=registry)
        )
        unauthorized = capture_public_error(
            lambda: execute_plan(sensitive_plan(), request=request, registry=registry)
        )

    assert public_error_payload(unknown) == MEMBER_ERROR
    assert public_error_payload(unauthorized) == MEMBER_ERROR
    assert str(unknown) == MEMBER_ERROR["message"]
    assert str(unauthorized) == MEMBER_ERROR["message"]
    assert "missing.private_field" not in repr(unknown)
    assert "customer.email" not in repr(unauthorized)
    assert unknown.__suppress_context__ is True
    assert unauthorized.__suppress_context__ is True
    assert "missing.private_field" not in "".join(traceback.format_exception(unknown))
    assert "customer.email" not in "".join(traceback.format_exception(unauthorized))


def test_parse_and_budget_failures_use_stable_codes(
    settings,
    django_assert_num_queries,
) -> None:
    """Structural and current-limit failures are distinguishable but safe."""

    registry = build_registry()
    request = request_with("shop.view_orders")
    settings.DJANGO_ASKLENS = {"MAX_ROWS": 1, "AUDIT_MODE": "disabled"}

    with django_assert_num_queries(0):
        parse_error = capture_public_error(
            lambda: execute_plan(b'{"resource":', request=request, registry=registry)
        )
        budget_error = capture_public_error(
            lambda: execute_plan(
                status_plan(limit=2), request=request, registry=registry
            )
        )

    assert public_error_payload(parse_error) == {
        "code": "asklens.parse.invalid",
        "message": "The query plan could not be parsed.",
    }
    assert public_error_payload(budget_error) == {
        "code": "asklens.budget.exceeded",
        "message": "The query plan exceeds an execution limit.",
    }


def test_missing_current_request_uses_authorization_code(
    django_assert_num_queries,
) -> None:
    """Explicitly missing trusted request context fails safely before SQL."""

    with django_assert_num_queries(0):
        error = capture_public_error(
            lambda: execute_plan(
                status_plan(),
                request=None,
                registry=build_registry(),
            )
        )

    assert public_error_payload(error) == {
        "code": "asklens.authorization.denied",
        "message": "The current request is not authorized to execute this query.",
    }


def test_scope_compilation_and_execution_failures_hide_internal_causes(
    monkeypatch,
    django_assert_num_queries,
) -> None:
    """Execution stages normalize unexpected internal failures safely."""

    registry = CatalogRegistry()

    def unavailable_scope(_request):
        raise RuntimeError("secret tenant scope implementation")

    registry.register(
        model=Order,
        name="orders",
        fields={"id": {"label": "ID"}, "status": {"label": "Status"}},
        metrics=[Metric("order_count", op="count", field="id")],
        scope_mode="context_scoped",
        scope_provider=unavailable_scope,
    )
    request = request_with()

    with django_assert_num_queries(0):
        scope_error = capture_public_error(
            lambda: execute_plan(status_plan(), request=request, registry=registry)
        )

    assert public_error_payload(scope_error) == {
        "code": "asklens.scope.unavailable",
        "message": "A safe query scope is unavailable for this request.",
    }
    assert "secret tenant" not in repr(scope_error)

    working_registry = build_registry()
    working_request = request_with("shop.view_orders")
    monkeypatch.setattr(
        "django_asklens.execution.runner._compile_prepared_query",
        lambda _prepared: (_ for _ in ()).throw(
            RuntimeError("secret compiler implementation")
        ),
    )
    with django_assert_num_queries(0):
        compile_error = capture_public_error(
            lambda: execute_plan(
                status_plan(),
                request=working_request,
                registry=working_registry,
            )
        )

    assert public_error_payload(compile_error) == {
        "code": "asklens.compile.failed",
        "message": "The query plan could not be compiled.",
    }
    assert "secret compiler" not in repr(compile_error)

    monkeypatch.undo()
    monkeypatch.setattr(
        "django_asklens.execution.runner._execute_compiled_query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("secret database implementation")
        ),
    )
    with django_assert_num_queries(0):
        execute_error = capture_public_error(
            lambda: execute_plan(
                status_plan(),
                request=working_request,
                registry=working_registry,
            )
        )

    assert public_error_payload(execute_error) == {
        "code": "asklens.execute.failed",
        "message": "The query could not be executed.",
    }
    assert "secret database" not in repr(execute_error)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (PlanParseError("diagnostic"), "asklens.parse.invalid"),
        (PermissionDeniedError("diagnostic"), "asklens.member.unavailable"),
        (PlanValidationError("diagnostic"), "asklens.plan.invalid"),
        (AuthorizationDeniedError("diagnostic"), "asklens.authorization.denied"),
        (BudgetExceededError("diagnostic"), "asklens.budget.exceeded"),
        (ScopeUnavailableError("diagnostic"), "asklens.scope.unavailable"),
        (BindingInvalidError("diagnostic"), "asklens.binding.invalid"),
        (CompilationError("diagnostic"), "asklens.compile.failed"),
        (ExecutionError("diagnostic"), "asklens.execute.failed"),
        (LLMProviderError("diagnostic"), "asklens.provider.failed"),
    ],
)
def test_typed_errors_have_stable_namespaced_codes(error, code: str) -> None:
    """Every accepted R1 execution category has a stable underlying code."""

    assert error.code == code
    payload = public_error_payload(error)
    assert payload["code"] == code
    assert "diagnostic" not in str(payload)


def test_public_error_payload_includes_only_a_safe_optional_pointer() -> None:
    """Public errors expose code, safe message, and optional JSON Pointer only."""

    error = PlanValidationError("internal field detail", pointer="/filters/0")

    assert public_error_payload(error) == {
        "code": "asklens.plan.invalid",
        "message": "The query plan is invalid.",
        "pointer": "/filters/0",
    }
