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
- `base_queryset`: request-aware hook for tenant and row-level scoping.

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
}
```

Defaults are conservative for catalog exposure: sensitive fields and hidden fields are not included in normal planner catalog serialization.

## Metrics

MVP aggregate queries must use explicit `Metric(...)` definitions.

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
