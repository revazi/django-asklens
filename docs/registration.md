# Registration API

The catalog is AskLens' source of truth. It defines which Django models, fields, metrics, and explicit resource scope policies are available to planning, validation, compilation, and API responses.

## `register()`

```python
from django_asklens import Metric, register

resource = register(
    model=Order,
    name="orders",
    label="Orders",
    description="Customer orders",
    synonyms=["sales", "purchases"],
    default_date_field="created_at",
    fields={
        "id": {"label": "Order ID"},
        "status": {"label": "Status"},
        "created_at": {"label": "Created date"},
        "total": {"label": "Order total", "metric": True},
    },
    metrics=[Metric("order_count", op="count", field="id")],
    default_order=(("created_at", "desc"),),
    requires_permission="orders.view_reports",
    scope_mode="context_scoped",
    scope_provider=lambda request: Order.objects.filter(
        account=request.user.account
    ),
)
```

### Arguments

- `model`: Django model class to expose as a semantic resource.
- `fields`: explicit allowlist of field paths. Relation paths such as `customer.name` are allowed when they validate against the model.
- `name`: stable plan-facing key. If omitted, AskLens derives one from the label/model name.
- `label`: human-readable display label.
- `description`: optional planner/user-facing description.
- `synonyms`: optional alternate words for the resource.
- `default_date_field`: registered date/datetime field used by date-oriented planning.
- `metrics`: explicit aggregate metrics available to plans.
- `default_order`: optional semantic `(field, "asc" | "desc")` pairs used when a list plan omits ordering. Fields must be unrestricted, result-visible registered fields.
- `row_identity`: optional private concrete non-null unique model field used as a final list tie-breaker. Defaults to the model primary key and is not serialized to catalogs/providers.
- `requires_permission`: optional permission string required to see and query the whole resource.
- `scope_mode`: required scope policy: `"global"` or `"context_scoped"`. There is no default.
- `scope_provider`: trusted request-aware queryset provider required for `context_scoped`; forbidden for `global`.
- `scope_resource`: optional capabilities/help metadata. Set `True` when this resource represents the scoped entity itself, regardless of what your project calls that entity.
- `examples_enabled`: optional boolean, default `True`. Set `False` for helper/lookup resources that should remain queryable but should not generate deterministic “suggested question” examples.

## Field metadata

Supported field config keys:

```python
{
    "label": "Customer email",
    "type": "string",
    "sensitive": True,
    "llm_visible": False,
    "result_visible": False,
    "filter_only": True,
    "requires_permission": "customers.view_pii",
    "metric": False,
    "scope_dimension": False,
}
```

Defaults are conservative for catalog exposure: sensitive fields and hidden fields are not included in normal planner catalog serialization.

## Resource and field permissions

Use resource-level `requires_permission` when the entire resource should be visible/queryable only to users with a permission string:

```python
register(
    model=Order,
    name="orders",
    fields={"id": {"label": "Order ID"}},
    requires_permission="orders.view_reports",
    scope_mode="context_scoped",
    scope_provider=lambda request: Order.objects.filter(
        account=request.user.account
    ),
)
```

Use field-level `requires_permission` for individual fields that need stronger access than the resource:

```python
fields={
    "status": {"label": "Status"},
    "customer.email": {
        "label": "Customer email",
        "sensitive": True,
        "requires_permission": "customers.view_pii",
    },
}
```

By default, AskLens checks `request.user.get_all_permissions()` in the API flow. If your project uses role tables, tenant-scoped grants, or another permission system, configure `DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"]`; see [Multi-tenant security](multitenancy-security.md).

Use `scope_dimension=True` for any field that identifies the user's row scope, whatever your schema calls it, such as `account.name`, `organization.title`, `gym.label`, or another project-specific relation. Use `scope_resource=True` when the whole resource represents the scoped entity. These flags only shape capabilities/help examples; row access is enforced by the resource's explicit `scope_mode` and trusted `scope_provider(request)`.

## Metrics

Aggregate queries currently use explicit `Metric(...)` definitions.

```python
Metric("revenue", op="sum", field="total", label="Revenue")
Metric("avg_order_value", op="avg", field="total")
```

Supported metric operations are `count`, `sum`, `avg`, `min`, and `max`.

## Explicit resource scope

Every registration must choose one mode:

```python
# Reviewed as intentionally unrestricted across rows.
register(
    model=Currency,
    fields={"code": {}, "name": {}},
    scope_mode="global",
)

# Restricted using current server-owned request context.
def visible_orders(request):
    return Order.objects.filter(account=request.user.account)


register(
    model=Order,
    fields={"id": {}, "status": {}},
    scope_mode="context_scoped",
    scope_provider=visible_orders,
)
```

A context scope provider must return an unevaluated Django `QuerySet` for the registered model. `Model.objects.none()` is valid. Returning `None`, a list, an evaluated queryset, or a queryset for another model fails with `asklens.scope.unavailable`; missing request context and provider exceptions also fail closed. AskLens never accepts client-provided tenant IDs or scope tokens as trusted scope.

The legacy `base_queryset=` argument is rejected with migration guidance. Replace it with `scope_mode="context_scoped"` and `scope_provider=...`. Intentionally unrestricted resources must explicitly use `scope_mode="global"`; omission never falls back to the default manager.

## Deterministic ordering

When a list plan omits `order_by`, AskLens applies the registered semantic `default_order`, then appends the private `row_identity` when missing. Explicit plan ordering remains primary but also receives the identity tie-breaker. If no semantic default is configured, identity-only ordering is still deterministic.

```python
register(
    model=Order,
    fields={"status": {}, "created_at": {}},
    scope_mode="context_scoped",
    scope_provider=visible_orders,
    default_order=(("created_at", "desc"),),
    # row_identity="public_id",  # only if concrete, non-null, unconditionally unique
)
```

Grouped aggregates append missing group keys as tie-breakers. Nulls sort last in both ascending and descending order. AskLens does not use `Meta.ordering` and provides no `assume_unique` escape hatch.

Do not rely on AskLens as the only tenant boundary; keep normal Django authentication, permissions, read-only database defense, and application-specific scope tests in place.
