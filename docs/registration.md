# Registration API

The catalog is AskLens' source of truth. It defines which Django models, fields, metrics, and explicit resource scope policies are available to planning, validation, compilation, and API responses.

## Start with one scoped field

In your host-owned registration module, import your `Order` model and define a
reviewed `visible_orders(request)` returning a lazy queryset of that model,
filtered by trusted current-request membership (see the
[working owner-scoped example](quickstart-app.md#6-inspect-registration-and-audit-then-use-your-model)).
Then register only the fields you intend to expose:

<!-- asklens-registration:minimal -->
```python
from django_asklens import register

resource = register(
    model=Order,
    name="orders",
    timezone="UTC",
    fields={
        "status": {"binding": "status", "type": "string", "nullable": False},
    },
    requires_permission="orders.view_reports",
    scope_mode="context_scoped",
    scope_provider=visible_orders,
)
```

This is an 11-line registration call with seven keyword arguments and one
three-entry field definition, excluding imports/model/scope-provider code. It
keeps a stable semantic name and a resource permission even though both arguments
are optional. It does **not** register the rest of the model. Every field still
needs an explicit private `binding`, canonical `type`, and boolean `nullable`;
these are exposure and validation decisions, not presentation boilerplate.

You can omit a field label when its default display text is suitable:
`status` becomes `Status`, `total_cents` becomes `Total Cents`, and
`customer.email` becomes `Customer Email`. Keep an explicit label when it adds
meaning, such as `Total (cents)`. A resource label defaults to the model's plural
verbose name in title case; keep `name` explicit so presentation/model renaming
does not rename your plan-facing resource. Metrics are optional and default to
none; add only reviewed aggregates, not every numeric field.

Projects whose resources are normally request-scoped can configure the safe mode once:

```python
DJANGO_ASKLENS = {
    "DEFAULT_SCOPE_MODE": "context_scoped",
}
```

`global` is intentionally not accepted as a project default. Every global resource must opt in explicitly.

## Startup import ownership

`django_asklens.apps.AskLensConfig` does not autodiscover host models or registration modules. Keep one project-owned registration module and import it through one host `AppConfig.ready()` path. Do not import the same module through models, URLs, admin, multiple app configs, or a manually invoked autoreloader path: duplicate process-local resource registration raises an error and must not be hidden by broad exception handling.

The [core-only executable quickstart](quickstart-core.md) shows the complete `apps.py` and registration-module wiring. Identity, permissions, and context scope remain server-owned; startup wiring must not accept them from plan or client input.

After startup, run `python manage.py check_asklens --fail-on-empty` to require at least one registered resource. The command reports aggregate counts only; it does not query application data, invoke scope providers, or expose names, bindings, permissions, or tenant metadata. Django runs host app initialization before the command handler, so this does not certify arbitrary `AppConfig.ready()` code as side-effect-free.

## `register()`

<!-- asklens-registration:reference -->
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

Only canonical values and explicitly listed aliases are accepted in `eq`, `neq`, and `in`. Aliases normalize to the canonical value; labels are display metadata and are not accepted unless also listed as aliases. Ambiguous aliases and duplicate canonical values fail registration. Django model `choices` are never copied or treated as aliases automatically; register an explicit enum or use open `string`/`integer` semantics deliberately.

Review the public subset of values and aliases individually. Do not generate
`values` from all model choices just to shorten registration: a choice may be
internal, and a translated/display label is not an input policy. Omitting a
choice from an explicit enum hides it from that field's catalog and rejects it
as filter input. Open `string`/`integer` fields are not choice allowlists: a label
is just an ordinary literal, not a normalized canonical choice. Enum metadata
and filter validation do not replace row scope or result-visibility policy.

Defaults remain conservative for catalog exposure: sensitive fields and hidden fields are not included in normal planner catalog serialization. Aggregate backing is declared only on `Metric` registrations.

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

A metric's private binding does not need a corresponding selectable field.
For example, register `revenue` backed by `total` without exposing individual
order totals. Put any stronger permission on the **metric itself**; AskLens does
not infer metric permissions from another field bound to the same Django path.
Resource permissions still apply. Omitting `label` gives `Revenue`; omitting
`cardinality_policy` retains `to_one_only`. Do not remove permission or
cardinality decisions merely to shorten the declaration.

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

Intentionally unrestricted resources must explicitly use `scope_mode="global"`; the project default cannot be `global`, and omission never falls back to the default manager.

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

## Before/after: less presentation boilerplate, same policy

The [installed-package quickstart](quickstart-app.md) uses the same public
registration APIs. With `register`, `Order`, and `visible_orders` from its
`shop/asklens_registration.py`, the original registration was:

<!-- asklens-registration:before -->
```python
register(
    model=Order,
    name="orders",
    label="My orders",
    description="Synthetic orders owned by the current authenticated user.",
    timezone="UTC",
    fields={
        "product": {
            "binding": "product",
            "type": "string",
            "nullable": False,
            "label": "Product",
        },
        "status": {
            "binding": "status",
            "type": "string",
            "nullable": False,
            "label": "Status",
        },
        "total_cents": {
            "binding": "total_cents",
            "type": "integer",
            "nullable": False,
            "label": "Total (cents)",
        },
    },
    default_order=(("product", "asc"),),
    requires_permission="shop.view_order",
    scope_mode="context_scoped",
    scope_provider=visible_orders,
)
```

The current example removes only two redundant labels and compacts those field
mappings. All metadata, private bindings, scope and permissions are identical:

<!-- asklens-registration:after -->
```python
register(
    model=Order,
    name="orders",
    label="My orders",
    description="Synthetic orders owned by the current authenticated user.",
    timezone="UTC",
    fields={
        "product": {"binding": "product", "type": "string", "nullable": False},
        "status": {"binding": "status", "type": "string", "nullable": False},
        "total_cents": {
            "binding": "total_cents",
            "type": "integer",
            "nullable": False,
            "label": "Total (cents)",
        },
    },
    default_order=(("product", "asc"),),
    requires_permission="shop.view_order",
    scope_mode="context_scoped",
    scope_provider=visible_orders,
)
```

### Measured friction and API decision (#189)

The reproducible baseline is source commit `f6ad3d2` (after #184/#186 onboarding
and adapter work). Count the `register(...)` AST node's inclusive source lines
and keyword arguments; count each field mapping's entries separately. Imports,
model definitions and the reviewed scope provider are excluded, not eliminated:

| Example | Call lines | Keyword arguments | Fields / field entries |
| --- | --- | --- | --- |
| Quickstart before | 31 | 10 | 3 / 12 |
| Quickstart after | 21 | 10 | 3 / 10 |
| One-field scoped example above | 11 | 7 | 1 / 3 |
| Original feature-rich `register()` reference above | 53 | 12 | 4 / 17 |

Nine of the quickstart's original 12 field entries are mandatory binding/type/
nullability decisions; two of its three labels merely repeat defaults. The
10-line reduction is mostly layout, **not** ten fewer policy decisions. These
are structural measurements, not onboarding timings or external usability
results; no independent user session is claimed.

| Repeated work or confusion | Existing API / better guidance, rather than a new helper |
| --- | --- |
| Verbose field dictionaries look mandatory in full | Compact mappings already work; omit only derived labels. `register()` and `CatalogRegistry.register()` share validation through `SemanticResource.build()`. Prebuilt field specs still require explicit bindings/types/nullability; they are not a model-discovery shortcut. |
| Numeric fields seem to require both selection and aggregate declarations | `Metric` already supports private backing without selectable exposure. Its operation, result type and permission are independent reviewed decisions. |
| Resource, field and metric permission strings look repetitive | They protect different surfaces. Resource permission gates the whole resource; stronger field/metric grants belong on each exposed member. Never infer grants or derive them from client input. |
| Django choices look like a ready-made public enum | Review a safe subset and explicit aliases; do not copy hidden values or treat display labels as accepted aliases. |
| Registration imports seem needed in each adapter | One host `AppConfig.ready()` import serves all adapters; no AskLens autodiscovery. Normal repeated Python imports are cached; re-executing registration still raises a duplicate error. Require nonempty registration explicitly with `check_asklens --fail-on-empty`. |

**Compatibility classification:** documentation, source example and tests only;
no new helper, governed signature/default change, migration, or broader exposure.
These forms use existing supported `0.3.x` behavior; the expanded guide and
source-example edit are not additions to immutable published artifacts. Existing
helpers already remove presentation defaults while keeping policy explicit, so
another wrapper would duplicate them without removing the measured trust
choices. Revisit helpers only with concrete friction that cannot be addressed
by these forms. See the [0.3.x compatibility boundary](compatibility.md).

Invalid declarations and duplicates must still abort initialization; do not catch
and ignore their errors. A missing import does not by itself abort all Django
startup: require the nonempty registry check and test the actual request path.
A green registry check does not certify scope-provider behavior or authorize a
query. Send every stored, cached or previously previewed plan through
`execute_plan()` with the current request: catalog membership, permissions,
scope and budgets are revalidated before application-data execution.
