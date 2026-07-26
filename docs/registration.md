# Registration API

The catalog is AskLens' source of truth. It defines which Django models, fields, metrics, and explicit resource scope policies are available to planning, validation, compilation, and API responses.

Projects whose resources are normally request-scoped can configure the safe mode once:

```python
DJANGO_ASKLENS = {
    "DEFAULT_SCOPE_MODE": "context_scoped",
}
```

`global` is intentionally not accepted as a project default. Every global resource must opt in explicitly.

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
        "order_id": {
            "binding": "id",
            "type": "integer",
            "nullable": False,
            "label": "Order ID",
        },
        "status": {
            "binding": "status",
            "type": "string",
            "nullable": False,
            "label": "Status",
        },
        "created_at": {
            "binding": "created_at",
            "type": "datetime",
            "nullable": False,
            "label": "Created date",
        },
        "total": {
            "binding": "total",
            "type": "decimal",
            "nullable": False,
            "label": "Order total",
            "metric": True,
        },
    },
    metrics=[Metric("order_count", op="count", field="order_id")],
    default_order=(("created_at", "desc"),),
    requires_permission="orders.view_reports",
    scope_provider=lambda request: Order.objects.filter(account=request.user.account),
)
```

### Arguments

- `model`: Django model class to expose as a semantic resource.
- `fields`: explicit mapping of stable public semantic keys to field definitions. Every definition requires a private Django `binding`, canonical `type`, and boolean `nullable`. Public dotted keys have no ORM meaning; private relationship bindings use Django `__` syntax.
- `name`: stable plan-facing key. If omitted, AskLens derives one from the label/model name.
- `label`: human-readable display label.
- `description`: optional planner/user-facing description.
- `synonyms`: optional alternate words for the resource.
- `default_date_field`: registered date/datetime field used by date-oriented planning.
- `metrics`: explicit aggregate metrics available to plans.
- `default_order`: optional semantic `(field, "asc" | "desc")` pairs used when a list plan omits ordering. Fields must be unrestricted, result-visible registered fields.
- `row_identity`: optional private concrete non-null unique model field used as a final list tie-breaker. Defaults to the model primary key and is not serialized to catalogs/providers.
- `requires_permission`: optional permission string required to see and query the whole resource.
- `scope_mode`: optional per-resource override. It must be `"global"` or `"context_scoped"`. When omitted, AskLens uses `DJANGO_ASKLENS["DEFAULT_SCOPE_MODE"]`; only `"context_scoped"` is accepted as a project default. If neither is configured, registration fails.
- `scope_provider`: trusted request-aware queryset provider required for `context_scoped`; forbidden for `global`.
- `scope_resource`: optional capabilities/help metadata. Set `True` when this resource represents the scoped entity itself, regardless of what your project calls that entity.
- `examples_enabled`: optional boolean, default `True`. Set `False` for helper/lookup resources that should remain queryable but should not generate deterministic “suggested question” examples.

## Field metadata

Supported field config keys:

```python
{
    "binding": "customer__email",
    "type": "string",
    "nullable": False,
    "label": "Customer email",
    "sensitive": True,
    "llm_visible": False,
    "result_visible": False,
    "filter_only": True,
    "requires_permission": "customers.view_pii",
    "metric": False,
    "scope_dimension": False,
}
```

`binding`, model metadata, and permission tokens remain server-owned and are never serialized into public catalogs, capabilities, or provider prompts. A binding change does not require a plan change. Registration rejects omitted bindings/types/nullability, invalid Django paths, unsupported type labels, and a non-null semantic declaration backed by a nullable field or traversal. Canonical type labels are `string`, `boolean`, `integer`, `decimal`, `float`, `date`, `datetime`, `time`, `uuid`, and `enum`; enum value registration is completed separately in the remaining 0.2 semantic work.

Defaults remain conservative for catalog exposure: sensitive fields and hidden fields are not included in normal planner catalog serialization.

### Migrating 0.1 field registrations

The 0.1 form used each mapping key as both public name and Django path:

```python
fields = {
    "id": {"label": "Order ID"},
    "customer.email": {"label": "Customer email"},
}
```

The 0.2 form separates those responsibilities explicitly:

```python
fields = {
    "order_id": {
        "binding": "id",
        "type": "integer",
        "nullable": False,
        "label": "Order ID",
    },
    "customer.email": {
        "binding": "customer__email",
        "type": "string",
        "nullable": False,
        "label": "Customer email",
    },
}
```

There is no implicit key-to-binding migration fallback. Missing metadata fails registration with developer-facing guidance. Update metrics, defaults, and plans only when you deliberately rename a public semantic key; changing `binding` alone does not change those references. The former `include_internal=True` catalog option is removed because public serialization no longer exposes model labels. Permission declarations continue to enforce visibility but are no longer copied into public catalog/capability payloads.

## Resource and field permissions

Use resource-level `requires_permission` when the entire resource should be visible/queryable only to users with a permission string:

```python
register(
    model=Order,
    name="orders",
    fields={
        "order_id": {
            "binding": "id",
            "type": "integer",
            "nullable": False,
            "label": "Order ID",
        }
    },
    requires_permission="orders.view_reports",
    scope_provider=lambda request: Order.objects.filter(account=request.user.account),
)
```

Use field-level `requires_permission` for individual fields that need stronger access than the resource:

```python
fields = {
    "status": {
        "binding": "status",
        "type": "string",
        "nullable": False,
        "label": "Status",
    },
    "customer.email": {
        "binding": "customer__email",
        "type": "string",
        "nullable": False,
        "label": "Customer email",
        "sensitive": True,
        "requires_permission": "customers.view_pii",
    },
}
```

By default, AskLens checks `request.user.get_all_permissions()` in the API flow. If your project uses role tables, tenant-scoped grants, or another permission system, configure `DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"]`; see [Multi-tenant security](multitenancy-security.md).

Use `scope_dimension=True` for any field that identifies the user's row scope, whatever your schema calls it, such as `account.name`, `organization.title`, `gym.label`, or another project-specific relation. Use `scope_resource=True` when the whole resource represents the scoped entity. These flags only shape capabilities/help examples; row access is enforced by the resource's effective `scope_mode` and trusted `scope_provider(request)`.

## Metrics

Aggregate queries currently use explicit `Metric(...)` definitions.

```python
Metric("revenue", op="sum", field="total", label="Revenue")
Metric("avg_order_value", op="avg", field="total")
```

Supported metric operations are `count`, `sum`, `avg`, `min`, and `max`.

## Fail-closed resource scope

Every resource must resolve to one mode. A resource can declare it directly, or it can inherit the safe `context_scoped` project default shown above:

```python
# Reviewed as intentionally unrestricted across rows.
register(
    model=Currency,
    fields={
        "code": {"binding": "code", "type": "string", "nullable": False},
        "name": {"binding": "name", "type": "string", "nullable": False},
    },
    scope_mode="global",
)


# Restricted using current server-owned request context.
def visible_orders(request):
    return Order.objects.filter(account=request.user.account)


register(
    model=Order,
    fields={
        "id": {"binding": "id", "type": "integer", "nullable": False},
        "status": {"binding": "status", "type": "string", "nullable": False},
    },
    # Inherits DEFAULT_SCOPE_MODE="context_scoped".
    scope_provider=visible_orders,
)
```

A context scope provider must return an unevaluated Django `QuerySet` for the registered model. `Model.objects.none()` is valid. Returning `None`, a list, an evaluated queryset, or a queryset for another model fails with `asklens.scope.unavailable`; missing request context and provider exceptions also fail closed. AskLens never accepts client-provided tenant IDs or scope tokens as trusted scope.

The legacy `base_queryset=` argument is rejected with migration guidance. Replace it with a context-scoped registration and `scope_provider=...`. Intentionally unrestricted resources must explicitly use `scope_mode="global"`; the project default cannot be `global`, and omission never falls back to the default manager.

## Deterministic ordering

When a list plan omits `order_by`, AskLens applies the registered semantic `default_order`, then appends the private `row_identity` when missing. Explicit plan ordering remains primary but also receives the identity tie-breaker. If no semantic default is configured, identity-only ordering is still deterministic.

```python
register(
    model=Order,
    fields={
        "status": {"binding": "status", "type": "string", "nullable": False},
        "created_at": {
            "binding": "created_at",
            "type": "datetime",
            "nullable": False,
        },
    },
    scope_provider=visible_orders,
    default_order=(("created_at", "desc"),),
    # row_identity="public_id",  # only if concrete, non-null, unconditionally unique
)
```

Grouped aggregates append missing group keys as tie-breakers. Nulls sort last in both ascending and descending order. AskLens does not use `Meta.ordering` and provides no `assume_unique` escape hatch.

Do not rely on AskLens as the only tenant boundary; keep normal Django authentication, permissions, read-only database defense, and application-specific scope tests in place.
