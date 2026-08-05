# Migrating from 0.1 alpha to 0.2 alpha

This guide covers the intentional alpha-breaking changes from the published
`0.1.0a1` shape to the current 0.2 target. AskLens supports one strict current
shape; it does not add embedded document versions, compatibility parsers, or
unsafe fallbacks.

Treat 0.2 as a strict replacement, not an in-place wire-compatible upgrade. Before changing a deployment, inventory every registration, direct Python import, saved/browser/client plan, dummy/provider fixture, API consumer, MCP integration, and audit-content policy. Rewrite them to the current shape in a staging environment, run Django migration planning and a database backup under the host's normal process, then run application-specific tenant/permission and PostgreSQL tests. Do not deploy old and new workers against shared persisted plans unless the host has explicitly migrated those plans; AskLens does not negotiate both shapes. Rollback means restoring the prior package, application registrations/clients, and any host-owned persisted plans together.

The source-checkout package smoke installs published `0.1.0a1` and force-replaces it with the current local wheel because the repository version cannot change before a separate release authorization. This exercises packaging/import replacement only.

For PR10 this script extension adds a disposable SQLite migration-state check inside its existing temporary working directory: it applies the already-published `0001_initial` and `0002_add_admin_query_proxy` migration set, writes one synthetic `SemanticQueryRun`, performs same-version local-wheel replacement, and re-runs `migrate --plan`, `migrate`, `showmigrations`, `check`, and `makemigrations --check --dry-run`. It then asserts one surviving synthetic row, a clean migration recorder state, and proxy/table shape expectations.

A real candidate version must rerun migration evidence as a normal resolver-selected upgrade against authorized host data and cannot infer PostgreSQL coverage from this SQLite probe. This check is package-state preservation evidence only, not a normal 0.1→0.2 upgrade pathway evidence.

## 1. Use the trusted execution facade

Replace direct compiler/executor usage with:

```python
from django_asklens.execution import execute_plan

result = execute_plan(untrusted_plan, request=request)
```

`compile_query_plan`, public `CompiledQuery`, and `execute_query` are removed.
`run_query_plan` remains temporarily as a deprecated wrapper, requires the
current request, and revalidates input.

Every plan remains untrusted, including an existing `QueryPlan`, saved plan,
provider output, API payload, and MCP payload.

## 2. Make resource policy and timezone explicit

Every resource must resolve to `global` or `context_scoped` and declare a
server-owned IANA timezone:

```python
register(
    model=Order,
    name="orders",
    timezone="UTC",
    scope_mode="context_scoped",
    scope_provider=visible_orders,
    fields=fields,
)
```

A project may set `DEFAULT_SCOPE_MODE="context_scoped"`, but every such resource
still needs a trusted `scope_provider(request)`. Every global resource must
explicitly declare `scope_mode="global"`; there is no global project default or
default-manager fallback. Replace legacy `base_queryset=` with
`scope_provider=`.

There is no resource-timezone default and no fallback to Django's `TIME_ZONE`.
Client plans cannot choose a timezone.

## 3. Separate semantic field keys from Django bindings

The 0.1 mapping key no longer doubles as an ORM path. Every field needs a
private binding, canonical type, and nullability:

```python
fields = {
    "customer.email": {
        "binding": "customer__email",
        "type": "string",
        "nullable": False,
        "label": "Customer email",
    }
}
```

Dotted public keys remain valid but have no traversal meaning. Bindings, model
labels, and permission tokens are not serialized to catalogs, capabilities, or
provider prompts.

Closed enums require explicit string/integer values and optional aliases.
Django `choices` are not exposed or accepted automatically.

## 4. Register metrics and reference only their names

Replace 0.1 client-defined metric objects:

```json
{"name": "revenue", "op": "sum", "field": "total"}
```

with:

```json
{"metric": "revenue"}
```

Registration owns operation, private binding, result type, permission,
distinct key, and relationship-cardinality policy. Legacy field-level
`metric=True` is rejected. To-many metrics fail closed except for the explicit
one-grain `count_rows` and private-key `count_distinct` policies.

## 5. Update canonical filter values and temporal input

Every filter requires a non-null `value`. Use `isnull` with a boolean instead of
`eq: null` or `neq: null`; `neq` excludes null rows.

Important value changes:

- Decimal values are finite strings.
- Float values are finite JSON numbers.
- UUIDs are canonical strings.
- Enum values are registered canonical values or explicit aliases.
- Dates use `YYYY-MM-DD`.
- Local times use offset-free `HH:MM:SS[.ffffff]`.
- Datetimes require an explicit RFC 3339 offset.
- Date ranges are inclusive; datetime ranges are half-open.
- QueryPlan `limit` is a positive JSON integer; booleans, floats, and numeric
  strings are not coerced.

Relative filters use the request-bound aware clock and resource timezone.
`last_n_days` is an exact rolling duration; `last_n_months` is calendar-month
subtraction with deterministic month-end and DST handling. Both exclude `now`
and future rows.

## 6. Move visualization out of QueryPlan

The old plan shape is rejected:

```json
{
  "resource": "orders",
  "intent": "aggregate",
  "visualization": {"type": "bar", "x": "status", "y": "order_count"}
}
```

Move display metadata to a sibling presentation envelope and rename `type` to
`kind`:

```json
{
  "query_plan": {
    "resource": "orders",
    "intent": "aggregate",
    "group_by": [{"field": "status"}],
    "metrics": [{"metric": "order_count"}]
  },
  "presentation": {
    "kind": "bar",
    "x": "status",
    "y": "order_count"
  }
}
```

This envelope is used by provider and `DUMMY_PLANS` responses. API/MCP clients
that submit their own plan send `plan` and optional `presentation` as sibling
fields. Use `include_presentation=false` to omit presentation from a response.

Legacy QueryPlan `visualization` is rejected with
`asklens.parse.invalid` and pointer `/visualization`. The inert
`DEFAULT_VISUALIZATION` setting is removed. Presentation never enters
the compiler or core `QueryResult` and cannot alter authorization, scope,
ordering, limits, execution, or returned values.

## 7. Update result consumers

Result metadata now uses:

```json
{"limit": 100, "limit_scope": "rows", "truncated": false}
```

Replace `limit_reached` checks with `truncated`. List and grouped queries fetch
one extra result to determine truncation; ungrouped aggregates have effective
limit one and never truncate.

Columns now include canonical `type` and `nullable`. Decimal results remain
strings. Aggregate decimal metrics may shed insignificant fractional trailing
zeros (`"20.00"` becomes `"20"`), while scalar decimal fields preserve scale
(`"20.00"` remains `"20.00"`). Empty ungrouped count is `0`; other empty
ungrouped aggregates are `null`; empty grouped aggregates return no rows.

`QueryResult.to_dict()` and `serialize_query_result()` return only core query
results. API/provider/MCP orchestration may add optional sibling
`presentation` metadata.

## 8. Review audit and error handling

Public execution failures expose stable `asklens.*` codes, a safe message, and
an optional JSON Pointer. Unknown and unauthorized members intentionally share
`asklens.member.unavailable`.

Database auditing stores operational metadata by default. Questions and full
plans require explicit `AUDIT_INCLUDE_CONTENT=True`; review retention and access
before enabling it.

## 9. Separate machine capabilities, catalog, and human help

The 0.1 capability payload mixed visible resources, operator facts, prose,
scope guidance, limitations, and examples. The current shape separates them:

- `build_capabilities()` and `GET /asklens/capabilities/` return only machine
  features and structural limits; `build_capabilities()` no longer accepts
  permissions, a registry, or a catalog.
- `serialize_catalog(permissions=...)` and `GET /asklens/catalog/` return
  permission-scoped resources, fields, enums, metrics, and timezones.
- Human guidance/examples are returned as `query_help` by help questions and
  remain internal to permission-scoped provider prompting.
- Query-help responses contain sibling `capabilities`, `catalog`, and
  `query_help` documents.
- MCP full discovery contains sibling `capabilities` and `catalog`; compact MCP
  discovery uses `capabilities` plus adapter-level `resource_summaries`.

Do not look for `resources`, `summary`, `examples`, labels, descriptions, or
scope guidance inside machine capabilities. Combine catalog field types with
machine type/operator entries when building a client-side planner.

## 10. Treat packaged schemas as one current internal shape

The package now includes Draft 2020-12 schemas named `catalog`, `query-plan`,
`capabilities`, `result`, and `error`, available through
`list_contract_schemas()` and `get_contract_schema(name)`. They contain no
embedded AskLens version or revision.

These schemas are internal, draft, and unfrozen. Do not treat them as a public
specification or as an authorization token. Existing plan consumers must still
migrate payloads to the current strict shape and execute through the trusted
facade.

## Migration checklist

- [ ] Route every executing adapter through `execute_plan()`.
- [ ] Add `timezone=` to every resource.
- [ ] Declare effective scope and every context scope provider.
- [ ] Add field `binding`, `type`, and `nullable` metadata.
- [ ] Move metric behavior into trusted registration.
- [ ] Update metric requests to `{ "metric": "name" }`.
- [ ] Update filter and temporal values to canonical forms.
- [ ] Move plan visualization to sibling presentation metadata.
- [ ] Update result consumers for `truncated`, typed columns, aggregate decimal
      canonicalization, scalar decimal scale preservation, and optional
      presentation.
- [ ] Read machine capabilities and permission-scoped catalog as separate
      documents; read human suggestions from `query_help`.
- [ ] Run tenant, permission, boundary, package, and PostgreSQL tests appropriate
      to the deployment before release.
