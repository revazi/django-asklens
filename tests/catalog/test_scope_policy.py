"""Fail-closed resource scope registration and execution tests."""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from django.db.models import QuerySet

from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import (
    InvalidResourceError,
    PublicAskLensError,
    ScopeUnavailableError,
)
from django_asklens.execution import execute_plan, run_query_plan
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def disable_audit(settings) -> None:
    """Keep scope-rejection query-count assertions in zero-total-SQL mode."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}


def order_plan() -> dict[str, Any]:
    """Return a minimal valid list plan for scope resolution tests."""

    return {
        "resource": "orders",
        "intent": "list",
        "select": ["id"],
        "limit": 10,
    }


def request_context() -> SimpleNamespace:
    """Return a request-like current context with no special permissions."""

    return SimpleNamespace(user=None)


def register_context_resource(
    scope_provider: Callable[[Any], QuerySet],
) -> CatalogRegistry:
    """Return a registry containing one explicitly context-scoped resource."""

    registry = CatalogRegistry()
    registry.register(
        timezone="UTC",
        model=Order,
        name="orders",
        fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
        scope_mode="context_scoped",
        scope_provider=scope_provider,
    )
    return registry


def test_scope_mode_is_required_at_registration() -> None:
    """Omitting scope policy must never imply the unrestricted manager."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="scope_mode is required"):
        registry.register(
            timezone="UTC",
            model=Order,
            name="orders",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
        )

    assert registry.all() == ()


def test_context_scoped_mode_can_be_configured_once(
    settings,
    django_assert_num_queries,
) -> None:
    """A safe project default avoids repeating context_scoped registrations."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "DEFAULT_SCOPE_MODE": "context_scoped",
    }
    registry = CatalogRegistry()

    resource = registry.register(
        timezone="UTC",
        model=Order,
        name="orders",
        fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
        scope_provider=lambda _request: Order.objects.none(),
    )

    assert resource.scope_mode == "context_scoped"
    assert resource.get_scope_queryset(request_context()).model is Order
    with django_assert_num_queries(0):
        result = execute_plan(
            order_plan(),
            request=request_context(),
            registry=registry,
        )
    assert result.rows == ()


def test_context_scoped_default_still_requires_provider(settings) -> None:
    """The project default must not weaken the trusted-provider requirement."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "DEFAULT_SCOPE_MODE": "context_scoped",
    }
    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="requires scope_provider"):
        registry.register(
            timezone="UTC",
            model=Order,
            name="orders",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
        )

    assert registry.all() == ()


def test_explicit_global_mode_overrides_context_scoped_default(settings) -> None:
    """Reviewed global resources remain explicit resource-level decisions."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "DEFAULT_SCOPE_MODE": "context_scoped",
    }
    registry = CatalogRegistry()

    resource = registry.register(
        timezone="UTC",
        model=Order,
        name="orders",
        fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
        scope_mode="global",
    )

    assert resource.scope_mode == "global"
    assert resource.get_scope_queryset(request_context()).model is Order


@pytest.mark.parametrize("default_scope_mode", ["global", "", "tenant", object()])
def test_default_scope_mode_must_be_context_scoped(
    settings,
    default_scope_mode: object,
) -> None:
    """A project default must never make omitted resource scope unrestricted."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "DEFAULT_SCOPE_MODE": default_scope_mode,
    }
    registry = CatalogRegistry()

    with pytest.raises(
        InvalidResourceError, match="DEFAULT_SCOPE_MODE.*context_scoped"
    ):
        registry.register(
            timezone="UTC",
            model=Order,
            name="orders",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            scope_provider=lambda _request: Order.objects.none(),
        )

    assert registry.all() == ()


@pytest.mark.parametrize(
    "legacy_base_queryset",
    [None, lambda _request: Order.objects.none()],
    ids=["explicit-none", "callable"],
)
def test_legacy_base_queryset_is_a_migration_error(
    legacy_base_queryset: object,
) -> None:
    """Any use of the legacy hook must not silently choose context scope."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="base_queryset.*scope_provider"):
        registry.register(
            timezone="UTC",
            model=Order,
            name="orders",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            base_queryset=legacy_base_queryset,
        )

    assert registry.all() == ()


@pytest.mark.parametrize("scope_mode", [None, "", "tenant", object()])
def test_scope_mode_must_be_global_or_context_scoped(scope_mode: object) -> None:
    """Unknown or malformed scope modes fail during registration."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="global.*context_scoped"):
        registry.register(
            timezone="UTC",
            model=Order,
            name="orders",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            scope_mode=scope_mode,
        )


def test_context_scoped_registration_requires_provider() -> None:
    """Context scope without a trusted provider is invalid."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="requires scope_provider"):
        registry.register(
            timezone="UTC",
            model=Order,
            name="orders",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            scope_mode="context_scoped",
        )


def test_global_registration_rejects_scope_provider() -> None:
    """Global must be an explicit unrestricted policy, not a hidden hook."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="global.*scope_provider"):
        registry.register(
            timezone="UTC",
            model=Order,
            name="orders",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            scope_mode="global",
            scope_provider=lambda _request: Order.objects.none(),
        )


def test_scope_provider_must_be_callable() -> None:
    """Context scope rejects non-callable provider configuration."""

    registry = CatalogRegistry()

    with pytest.raises(InvalidResourceError, match="scope_provider must be callable"):
        registry.register(
            timezone="UTC",
            model=Order,
            name="orders",
            fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
            scope_mode="context_scoped",
            scope_provider=object(),
        )


def test_explicit_global_scope_returns_default_manager_queryset() -> None:
    """Only explicit global scope may use the registered model manager."""

    registry = CatalogRegistry()
    resource = registry.register(
        timezone="UTC",
        model=Order,
        name="orders",
        fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
        scope_mode="global",
    )

    queryset = resource.get_scope_queryset(request_context())

    assert isinstance(queryset, QuerySet)
    assert queryset.model is Order


def test_deprecated_runner_rejects_missing_current_request_before_sql(
    django_assert_num_queries,
) -> None:
    """The compatibility path cannot execute even global scope without context."""

    registry = CatalogRegistry()
    registry.register(
        timezone="UTC",
        model=Order,
        name="orders",
        fields={"id": {"binding": "id", "type": "integer", "nullable": False}},
        scope_mode="global",
    )

    with (
        django_assert_num_queries(0),
        pytest.warns(DeprecationWarning, match="execute_plan"),
        pytest.raises(PublicAskLensError, match="not authorized") as caught,
    ):
        run_query_plan(order_plan(), registry=registry)

    assert caught.value.code == "asklens.authorization.denied"


def test_context_scope_requires_current_request() -> None:
    """A context-scoped resource cannot resolve without request context."""

    resource = register_context_resource(lambda _request: Order.objects.none()).get(
        "orders"
    )

    with pytest.raises(ScopeUnavailableError, match="current request"):
        resource.get_scope_queryset(None)


@pytest.mark.parametrize(
    ("scope_provider", "message"),
    [
        (lambda _request: None, "QuerySet"),
        (lambda _request: object(), "QuerySet"),
        (lambda _request: Customer.objects.all(), "registered model"),
    ],
    ids=["none", "not-queryset", "wrong-model"],
)
def test_invalid_scope_provider_result_rejects_before_sql(
    scope_provider: Callable[[Any], Any],
    message: str,
    django_assert_num_queries,
) -> None:
    """Invalid provider results fail closed without application-data SQL."""

    registry = register_context_resource(scope_provider)

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError, match="safe query scope") as caught,
    ):
        execute_plan(order_plan(), request=request_context(), registry=registry)

    assert caught.value.code == "asklens.scope.unavailable"
    assert message not in str(caught.value)


def test_evaluated_scope_queryset_rejects_before_sql(django_assert_num_queries) -> None:
    """The provider result must remain lazy when AskLens receives it."""

    def evaluated_scope(_request: Any) -> QuerySet:
        queryset = Order.objects.none()
        tuple(queryset)
        return queryset

    registry = register_context_resource(evaluated_scope)

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError, match="safe query scope") as caught,
    ):
        execute_plan(order_plan(), request=request_context(), registry=registry)

    assert caught.value.code == "asklens.scope.unavailable"


def test_scope_provider_failure_rejects_before_sql(django_assert_num_queries) -> None:
    """Provider exceptions become opaque scope errors and never broaden access."""

    def unavailable_scope(_request: Any) -> QuerySet:
        raise RuntimeError("private tenant diagnostic")

    registry = register_context_resource(unavailable_scope)

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError, match="safe query scope") as caught,
    ):
        execute_plan(order_plan(), request=request_context(), registry=registry)

    assert caught.value.code == "asklens.scope.unavailable"
    assert "tenant" not in str(caught.value)


def test_none_queryset_is_a_valid_context_scope(django_assert_num_queries) -> None:
    """A trusted provider may deliberately grant no rows."""

    registry = register_context_resource(lambda _request: Order.objects.none())

    with django_assert_num_queries(0):
        result = execute_plan(
            order_plan(), request=request_context(), registry=registry
        )

    assert result.rows == ()
