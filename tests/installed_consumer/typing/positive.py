"""Static-only host examples; never executed or imported by pytest.

Django's untyped Model is deliberately passed in rather than subclassed here.
No ORM, scope-provider, JSON-document or adapter typing guarantee is implied.
"""

from collections.abc import Mapping
from typing import Literal, assert_type

from django.db.models import Model

from django_asklens import Metric, SemanticResource, get_resource, register
from django_asklens.catalog import (
    CatalogRegistry,
    default_registry,
)
from django_asklens.catalog import (
    Metric as CatalogMetric,
)
from django_asklens.catalog import (
    SemanticResource as CatalogResource,
)
from django_asklens.catalog import (
    get_resource as catalog_get_resource,
)
from django_asklens.catalog import (
    register as catalog_register,
)
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import QueryResult, execute_plan
from django_asklens.observability import ObservabilityEvent

type ExpectedCode = Literal[
    "asklens.parse.invalid",
    "asklens.member.unavailable",
    "asklens.plan.invalid",
    "asklens.authorization.denied",
    "asklens.scope.unavailable",
    "asklens.budget.exceeded",
    "asklens.binding.invalid",
    "asklens.compile.failed",
    "asklens.execute.failed",
    "asklens.provider.failed",
]


def registration(model: type[Model]) -> None:
    metric = Metric(name="count", op="count", binding="id", result_type="integer")
    assert_type(metric, Metric)
    assert_type(CatalogMetric, type[Metric])
    assert_type(CatalogResource, type[SemanticResource])
    registry = CatalogRegistry()
    assert_type(default_registry, CatalogRegistry)
    resource = registry.register(
        model=model,
        name="orders",
        fields={"id": {"binding": "id"}},
        metrics=[metric],
        scope_mode="global",
        timezone="UTC",
        default_order=[("id", "asc")],
    )
    assert_type(resource, SemanticResource)
    assert_type(resource.name, str)
    assert_type(resource.metrics, Mapping[str, Metric])
    assert_type(registry.get("orders"), SemanticResource)
    assert_type(
        register(model=model, name="orders", fields={}, scope_mode="global"),
        SemanticResource,
    )
    assert_type(
        catalog_register(model=model, name="more", fields={}, scope_mode="global"),
        SemanticResource,
    )
    assert_type(get_resource("orders"), SemanticResource)
    assert_type(catalog_get_resource("orders"), SemanticResource)


def trusted_execution(request: object, registry: CatalogRegistry) -> QueryResult:
    # Plan contents and current host authorization still require runtime checks.
    try:
        result = execute_plan(
            {"resource": "orders", "intent": "list", "select": ["id"]},
            request=request,
            registry=registry,
        )
        assert_type(result, QueryResult)
        assert_type(result.row_count, int)
        assert_type(result.duration_ms, int)
        assert_type(result.limit, int)
        assert_type(result.limit_scope, Literal["rows", "groups"])
        assert_type(result.truncated, bool)
        # Container operations are typed; cell values/envelope contents are
        # intentionally dynamic, not asserted to be statically known JSON.
        for row in result.rows:
            for key in row:
                assert_type(key, str)
        result.to_dict()
        return result
    except PublicAskLensError as exc:
        payload = public_error_payload(exc)
        assert_type(payload["message"], str)
        assert_type(exc.pointer, str | None)
        if "pointer" in payload:
            assert_type(payload["pointer"], str)
        assert_type(payload["code"], ExpectedCode)
        assert_type(exc.code, ExpectedCode)
        raise


def observe(event: ObservabilityEvent) -> None:
    assert_type(event.resource, str | None)
    assert_type(event.intent, Literal["list", "aggregate"] | None)
    assert_type(event.duration_ms, int)
    assert_type(event.result_count, int | None)
    assert_type(event.truncated, bool | None)
    assert_type(
        event.name,
        Literal[
            "asklens.plan.accepted",
            "asklens.plan.rejected",
            "asklens.execution.succeeded",
            "asklens.execution.failed",
        ],
    )
    assert_type(event.status, Literal["accepted", "rejected", "succeeded", "failed"])
    assert_type(event.error_code, ExpectedCode | None)
