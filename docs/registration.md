# Registration API

The catalog is AskLens' source of truth. It defines which Django models, fields, metrics, and base querysets are available to planning, validation, compilation, and API responses.

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
    requires_permission="orders.view_reports",
    base_queryset=lambda request: Order.objects.filter(account=request.user.account),
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
- `requires_permission`: optional permission string required to see and query the whole resource.
- `base_queryset`: request-aware hook for tenant and row-level scoping.
- `scope_resource`: optional boolean. Set `True` when this resource represents the scoped entity itself, regardless of what your project calls that entity.
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
    base_queryset=lambda request: Order.objects.filter(account=request.user.account),
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

Use `scope_dimension=True` for any field that identifies the user's row scope, whatever your schema calls it, such as `account.name`, `organization.title`, `gym.label`, or another project-specific relation. Use `scope_resource=True` when the whole resource represents the scoped entity. These flags only shape capabilities/help examples; row access must still be enforced by `base_queryset(request)`.

## Metrics

Aggregate queries currently use explicit `Metric(...)` definitions.

```python
Metric("revenue", op="sum", field="total", label="Revenue")
Metric("avg_order_value", op="avg", field="total")
```

Supported metric operations are `count`, `sum`, `avg`, `min`, and `max`.

## Base querysets

Use `base_queryset(request)` for tenant scoping and row-level access rules. AskLens compilation starts from this queryset, not from a new unrestricted query.

```python
def visible_orders(request):
    return Order.objects.filter(account=request.user.account)
```

Do not rely on AskLens as the only tenant boundary; keep normal Django permissions and queryset scoping in place.
