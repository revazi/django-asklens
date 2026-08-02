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
    timezone="UTC",
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
            "type": "enum",
            "nullable": False,
            "label": "Status",
            "enum": {
                "type": "string",
                "values": [
                    {"value": "pending", "label": "Pending"},
                    {"value": "paid", "label": "Paid", "aliases": ["settled"]},
                ],
            },
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
        },
    },
    metrics=[
        Metric(
            "order_count",
            op="count",
            binding="id",
            result_type="integer",
        )
    ],
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
- `timezone`: required server-owned IANA timezone name, such as `"UTC"` or
  `"America/New_York"`. It is included in catalog and provider-guidance metadata
  so consumers can interpret calendar buckets, but plans cannot override it and
  AskLens never falls back to Django's `TIME_ZONE`.
- `metrics`: explicit aggregate metrics available to plans.
- `default_order`: optional semantic `(field, "asc" | "desc")` pairs used when a list plan omits ordering. Fields must be unrestricted, result-visible registered fields.
- `row_identity`: optional private concrete non-null unique model field used as a final list tie-breaker. Defaults to the model primary key and is not serialized to catalogs/providers.
- `requires_permission`: optional permission string required to see and query the whole resource.
- `scope_mode`: optional per-resource override. It must be `"global"` or `"context_scoped"`. When omitted, AskLens uses `DJANGO_ASKLENS["DEFAULT_SCOPE_MODE"]`; only `"context_scoped"` is accepted as a project default. If neither is configured, registration fails.
- `scope_provider`: trusted request-aware queryset provider required for `context_scoped`; forbidden for `global`.
- `scope_resource`: optional query-help/provider-guidance metadata. Set `True` when this resource represents the scoped entity itself, regardless of what your project calls that entity.
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
    "scope_dimension": False,
}
```

`binding`, model metadata, and permission tokens remain server-owned and are never serialized into public catalogs, capabilities, or provider prompts. A binding change does not require a plan change. Registration rejects omitted bindings/types/nullability, invalid Django paths, unsupported type labels, and a non-null semantic declaration backed by a nullable field or traversal. Canonical type labels are `string`, `boolean`, `integer`, `decimal`, `float`, `date`, `datetime`, `time`, `uuid`, and `enum`.

### Canonical operators and values

Capabilities list the supported operators for each visible field. The current matrix is:

| Type | Operators |
| --- | --- |
| `string` | `eq`, `neq`, `contains`, `icontains`, `in`, `isnull` |
| `boolean` | `eq`, `neq`, `in`, `isnull` |
| `integer`, `decimal`, `float`, `time` | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `isnull` |
| `date`, `datetime` | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `isnull`, `date_range`, `last_n_days`, `last_n_months` |
| `uuid`, `enum` | `eq`, `neq`, `in`, `isnull` |

Every filter requires a non-null `value`. String containment is not available on enums or other types. `eq: null` and `neq: null` are rejected; use `isnull` with a boolean value. `neq` excludes null rows. Integer inputs are JSON integers excluding booleans, decimal inputs are finite strings, float inputs are finite JSON numbers, UUID inputs normalize to canonical strings, and `in` validates every element against the field type.

Date values use strict `YYYY-MM-DD` strings, local time values use offset-free
`HH:MM:SS[.ffffff]` strings, and datetime values require RFC 3339 strings with
an explicit offset. Date ranges include both calendar dates;
datetime ranges are half-open `[start, end)`. Relative datetime filters use the
injected aware request clock: `last_n_days(N)` is the previous `N*24` hours and
`last_n_months(N)` subtracts calendar months at the same resource-local wall
clock time with month-end clamping. Both exclude `now` and future rows. For a
`date` field, relative instant bounds project to inclusive calendar dates in the
resource timezone. Day/month/quarter/year buckets use the resource timezone and
weeks begin Monday. If calendar-month subtraction lands in a nonexistent DST
wall time, the boundary moves forward by the transition gap; an ambiguous wall
time uses its earlier occurrence.

### Explicit enums

Enum metadata is mandatory when `type="enum"` and invalid on other field types:

```python
"status": {
    "binding": "status",
    "type": "enum",
    "nullable": False,
    "enum": {
        "type": "string",  # or "integer"; must match the private binding
        "values": [
            {"value": "pending", "label": "Pending"},
            {
                "value": "paid",
                "label": "Paid",
                "aliases": ["settled", "complete"],
            },
        ],
    },
}
```

Only canonical values and explicitly listed aliases are accepted in `eq`, `neq`, and `in`. Aliases normalize to the canonical value; labels are display metadata and are not accepted unless also listed as aliases. Ambiguous aliases and duplicate canonical values fail registration. Django model `choices` are never copied or treated as aliases automatically. Projects migrating choice-backed fields must either register an explicit enum or retain open `string`/`integer` semantics deliberately.

Defaults remain conservative for catalog exposure: sensitive fields and hidden fields are not included in normal planner catalog serialization. The legacy field-level `metric=True` flag is rejected; aggregate backing is declared only on `Metric` registrations.

### Migrating 0.1 field registrations

The 0.1 form used each mapping key as both public name and Django path:

```python
fields = {
    "id": {"label": "Order ID"},
    "customer.email": {"label": "Customer email"},
}
```

The 0.2 form separates those responsibilities explicitly and every resource
also adds `timezone="<IANA name>"` to its `register()` call:

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

There is no implicit key-to-binding migration fallback. Missing metadata fails registration with developer-facing guidance. Update defaults and plans only when you deliberately rename a public semantic key; changing a field binding alone does not change those references. Metric bindings are now independent trusted registration metadata rather than references to semantic fields. The former `include_internal=True` catalog option is removed because public serialization no longer exposes model labels. Permission declarations continue to enforce visibility but are no longer copied into public catalog/capability payloads.

## Resource and field permissions

Use resource-level `requires_permission` when the entire resource should be visible/queryable only to users with a permission string:

```python
register(
    timezone="UTC",
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

Use `scope_dimension=True` for any field that identifies the user's row scope, whatever your schema calls it, such as `account.name`, `organization.title`, `gym.label`, or another project-specific relation. Use `scope_resource=True` when the whole resource represents the scoped entity. These flags only shape query-help examples and provider guidance; row access is enforced by the resource's effective `scope_mode` and trusted `scope_provider(request)`.

## Metrics

Aggregate plans reference registered metrics by semantic name only:

```json
{"metrics": [{"metric": "revenue"}]}
```

The server-owned registration defines everything that could change query behavior:

```python
Metric(
    "revenue",
    op="sum",
    binding="total",
    result_type="decimal",
    label="Revenue",
    cardinality_policy="to_one_only",
    requires_permission="orders.view_financials",
)
```

`binding`, `op`, `result_type`, `distinct_key`, cardinality policy, and permission policy are never accepted from a plan. Public catalog and provider-guidance metric entries include only the semantic name, label, and result type; machine capabilities contain no resource metrics. Private Django paths and permission tokens are omitted from every document.

Supported operations are `count`, `sum`, `avg`, `min`, and `max`. The default `to_one_only` policy rejects any metric crossing a to-many relationship. The only 0.2 exceptions are explicit counts at one declared relationship grain:

```python
Metric(
    "line_count",
    op="count",
    binding="lines__id",
    result_type="integer",
    cardinality_policy="count_rows",
)
Metric(
    "distinct_products",
    op="count",
    binding="lines__product__id",
    result_type="integer",
    cardinality_policy="count_distinct",
    distinct_key="lines__product__id",
)
```

`count_rows` requires a non-null unique terminal key. `count_distinct` additionally requires a private non-null unique `distinct_key` at the same relationship grain. Numeric to-many aggregates, nested/independent fanout, implicit distinctness, and `allow_fanout` escape hatches are rejected.

### Migrating 0.1 metric plans

Replace client-supplied metric definitions:

```json
{"name": "revenue", "op": "sum", "field": "total"}
```

with the registered semantic reference:

```json
{"metric": "revenue"}
```

Move the operation and backing field into `Metric(binding=..., result_type=...)`. Old plan keys are rejected during structural parsing rather than compared with trusted registration.

## Fail-closed resource scope

Every resource must resolve to one mode. A resource can declare it directly, or it can inherit the safe `context_scoped` project default shown above:

```python
# Reviewed as intentionally unrestricted across rows.
register(
    timezone="UTC",
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
    timezone="UTC",
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
    timezone="UTC",
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
