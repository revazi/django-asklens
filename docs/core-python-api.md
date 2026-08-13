# Core Python API

Django AskLens can be used without Django REST Framework. Install the core package when you want to register semantic resources, ask a provider for catalog-validated `QueryPlan` JSON, execute read-only Django ORM queries, and serialize results from Python code.

> **Alpha trust-boundary warning:** `parse_query_plan()` establishes structure only. Use `execute_plan(plan, request=request)` for execution: it treats mappings and existing `QueryPlan` objects as untrusted and repeats current catalog, permission, limit, and request-scope validation. `run_query_plan()` remains temporarily as a deprecated safe wrapper. The compiler and compiled-query executor are internal and no longer public exports. Never treat a previously validated `QueryPlan` as a reusable authorization token.

```bash
python -m pip install django-asklens
```

Install `django-asklens[api]` only when you want the built-in DRF routes under `django_asklens.api` or the packaged reference frontend. For a fresh project with complete registration startup wiring, explicit global and context scope, string-select list plans, and an exact-wheel smoke, follow the [core-only executable quickstart](quickstart-core.md).

## Core-only Django setup

Add AskLens to `INSTALLED_APPS` and run migrations for query-run audit records:

```python
INSTALLED_APPS = [
    # ...
    "django_asklens",
]
```

```bash
python -m django migrate asklens
```

Do not include or import `django_asklens.api.urls` unless the `api` extra and `rest_framework` are installed.

AskLens does not autodiscover a host registration module. Import that module through one project-owned `AppConfig.ready()` path; do not also import it through models, URLs, admin, another app config, or manually invoked autoreloader code. See [Registration](registration.md#startup-import-ownership).

## Register resources

Register only reviewed models and fields. Configure the safe project default once when resources are normally request-scoped:

```python
DJANGO_ASKLENS = {
    "DEFAULT_SCOPE_MODE": "context_scoped",
}
```

Resources can override that setting, but `global` must always be explicit per resource. Use a trusted `scope_provider(request)` for tenant and row-level scope.

```python
from django_asklens import Metric, register
from shop.models import Order


def visible_orders(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return Order.objects.none()
    return Order.objects.filter(account__memberships__user=user)


register(
    timezone="UTC",
    model=Order,
    name="orders",
    label="Orders",
    description="Orders visible to the current user.",
    fields={
        "id": {
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
        },
        "customer.email": {
            "binding": "customer__email",
            "type": "string",
            "nullable": False,
            "label": "Customer email",
            "sensitive": True,
            "requires_permission": "customers.view_pii",
        },
    },
    metrics=[
        Metric(
            "order_count",
            op="count",
            binding="id",
            result_type="integer",
            label="Orders",
        ),
        Metric(
            "revenue",
            op="sum",
            binding="total",
            result_type="decimal",
            label="Revenue",
        ),
    ],
    requires_permission="orders.view_reports",
    scope_provider=visible_orders,
)
```

The field mapping key is the public semantic name used by plans. `binding` is trusted server-owned Django metadata, uses `__` for relationships, and is excluded from catalog, capability, and provider payloads. `type` and `nullable` are explicit public semantics rather than values inferred from the binding. Every resource also requires a server-owned IANA `timezone`, which is visible metadata but never client-controlled. Metric operation, binding, result type, permission, distinctness, and cardinality are also trusted registration metadata; untrusted plans contain only `{"metric": "registered_name"}`.

Validation enforces the capability-declared operator matrix and canonical JSON values before scope resolution. Decimal filter values are finite strings, floats are finite JSON numbers, UUIDs normalize canonically, dates and local times use strict ISO forms, datetimes require an explicit RFC 3339 offset, and `eq`/`neq` never accept null. Choice labels are not inferred from Django model metadata; use an explicit `type="enum"` definition with registered canonical values and aliases when closed-set semantics are intended. See [Registration](registration.md).

## Build machine capabilities and a permission-scoped catalog

Machine capabilities describe the installed implementation's supported intents,
canonical types/operators, time grains, structural limits, features, aggregate
policies, and backend restrictions. They deliberately contain no resources,
labels, descriptions, examples, or human guidance:

```python
from django_asklens import build_capabilities

capabilities = build_capabilities()
```

Build the current request's visible semantic catalog separately:

```python
from django_asklens import serialize_catalog
from django_asklens.permissions import get_request_permissions

permissions = get_request_permissions(request)
catalog = serialize_catalog(permissions=permissions)
```

Neither document contains rows or sample values. By default, AskLens reads
`request.user.get_all_permissions()` for authenticated users when constructing
the catalog and validating plans. Projects with role, tenant, or staff-grant
systems can configure `DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"]`.

## Read the draft internal JSON Schemas

The installed package includes the current Draft 2020-12 schemas for catalog,
query plan, capabilities, result, and error documents:

```python
from django_asklens import get_contract_schema, list_contract_schemas

names = list_contract_schemas()
plan_schema = get_contract_schema("query-plan")
```

These schemas are internal and unfrozen, carry no embedded contract version,
and do not replace trusted execution or current-request authorization. See
[Draft internal contract schemas](internal-contracts.md).

## Validate and execute a known plan

If your application already has a plan payload, pass the untrusted mapping directly to `execute_plan()`. The facade parses it and checks the current registered catalog, allowed fields, permissions, limits, relation depth, and read-only intent before compilation.

```python
from django_asklens.execution import execute_plan

payload = {
    "resource": "orders",
    "intent": "aggregate",
    "group_by": [{"field": "status"}],
    "metrics": [{"metric": "order_count"}],
    "order_by": [{"metric": "order_count", "direction": "desc"}],
    "limit": 10,
}

result = execute_plan(payload, request=request)
response_payload = result.to_dict()
```

`QueryResult.to_dict()` contains only core columns, rows, timing, limit metadata,
and the optional `empty: true` marker. Optional display metadata is a separate
presentation envelope and is never accepted by `execute_plan()` as part of
QueryPlan.

`execute_plan(...)` repeats current semantic validation and then resolves the resource's fail-closed scope policy. `global` uses the registered model manager only when deliberately declared on that resource. `context_scoped` may be inherited from `DEFAULT_SCOPE_MODE`, but still requires the current request and a trusted provider returning an unevaluated `QuerySet` for the registered model. Missing or invalid scope fails with `asklens.scope.unavailable` and never broadens to the default manager.

The legacy `base_queryset=` registration argument is rejected. Migrate it to a context-scoped registration with `scope_provider=...`; resources intentionally unrestricted across rows must declare `scope_mode="global"` explicitly.

### Structural budgets

Before scope resolution or ORM compilation, execution bounds UTF-8 plan bytes, filters, selected fields, order terms, groups, metrics, relationship-hop depth, unique relationship edges across the complete plan, values in each `in` filter, total scalar filter values, and returned rows/groups. Repeated meaningless select/filter/group/order/`in` references are rejected rather than used to evade counting.

Defaults are configurable implementation settings:

```python
DJANGO_ASKLENS = {
    "MAX_PLAN_BYTES": 65_536,
    "MAX_FILTERS": 20,
    "MAX_SELECTED_FIELDS": 25,
    "MAX_ORDER_BY": 5,
    "MAX_GROUP_BY": 3,
    "MAX_METRICS": 5,
    "MAX_JOINS": 2,
    "MAX_RELATIONSHIP_EDGES": 8,
    "MAX_IN_VALUES": 100,
    "MAX_FILTER_VALUES": 200,
    "MAX_ROWS": 500,
    "DEFAULT_LIMIT": 100,
}
```

`MAX_JOINS` is the maximum hop depth of any field reference; `MAX_RELATIONSHIP_EDGES` counts unique traversed relationship prefixes across all plan positions. `DEFAULT_LIMIT` is capped by `MAX_ROWS`. Structural budgets do not replace database statement/request timeouts, rate/concurrency limits, read-only credentials, indexes, or monitoring.

### Deterministic results and truncation

List plans use explicit plan ordering when present, otherwise the resource's semantic `default_order`; a private `row_identity` (the primary key by default) is appended when missing. Grouped aggregates append missing group keys. Nulls sort last for both directions.

List and grouped queries fetch one extra row/group, return at most the effective limit, and expose accurate metadata:

```json
{"limit": 100, "limit_scope": "rows", "truncated": false}
```

Ungrouped aggregates have effective limit one and always report `truncated: false`. An empty ungrouped aggregate returns one row with count metrics set to `0` and other aggregates set to `null`; an empty grouped aggregate returns no rows. Accurate truncation does not provide cursor pagination.

Serialized columns include canonical `type` and `nullable`. Decimal results remain strings. Runtime values that do not match the declared canonical type, nullability, enum values, or column set fail with `asklens.execute.failed` instead of being silently stringified.

### Migrating low-level alpha imports

Replace `from django_asklens.compiler import compile_query_plan` and `from django_asklens.execution import execute_query` with `execute_plan()`. `CompiledQuery` is also internal. AskLens intentionally provides no public operation that executes a caller-supplied compiled or merely shape-valid plan. `run_query_plan()` remains available for one alpha cycle, emits `DeprecationWarning`, requires the current request, and revalidates its input.

Do not infer truncation from `row_count == plan.limit` or the old
`build_result_metadata(plan=..., row_count=...)` helper shape. Consume the
trusted `result_metadata` returned directly by `QueryResult.to_dict()`, under
the HTTP shared-orchestrator `result` child, or in the MCP response.

### Stable execution errors

`execute_plan()` raises `PublicAskLensError` with a namespaced `code` and safe string message. Internal member names, permission tokens, scope implementation details, compiler causes, and database causes are not copied into this public exception.

```python
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import execute_plan

try:
    result = execute_plan(payload, request=request)
except PublicAskLensError as exc:
    error = public_error_payload(exc)
    # {"code": "asklens.member.unavailable", "message": "..."}
```

AskLens query-plan failures in the API and MCP helpers use the same `error` object with `code`, safe `message`, and an optional safe JSON `pointer`. The four AskLens DRF views wrap every handled HTTP failure as `{"error": {...}, "run_id"?: <database audit id>}`. Invalid or unknown-key query input and parser/media/method failures use `asklens.parse.invalid`; route authentication, permission, and debug denials use `asklens.authorization.denied`; throttling uses `asklens.budget.exceeded`. Status codes and applicable `Allow`, `WWW-Authenticate`, and `Retry-After` headers remain meaningful. This route-local adapter does not change non-AskLens host endpoints or the shared Python/MCP response shape. Unknown and unauthorized resources, fields, and metrics deliberately return the same `asklens.member.unavailable` error.

Current execution codes are `asklens.parse.invalid`, `asklens.member.unavailable`, `asklens.plan.invalid`, `asklens.authorization.denied`, `asklens.scope.unavailable`, `asklens.budget.exceeded`, `asklens.binding.invalid`, `asklens.compile.failed`, `asklens.execute.failed`, and `asklens.provider.failed`.

## Ask a provider, then execute

The planner uses the configured backend by default. The default `dummy` backend is deterministic and makes no network calls.

```python
from django_asklens.execution import execute_plan
from django_asklens.permissions import get_request_permissions
from django_asklens.planning import plan_question

permissions = get_request_permissions(request)
planner_result = plan_question("Show orders by status", permissions=permissions)
result = execute_plan(planner_result.plan, request=request)
payload = result.to_dict()
presentation = planner_result.presentation  # Separate; never executable.
```

The provider result is still untrusted: `plan_question(...)` validates provider output before returning a plan, and `execute_plan(...)` deliberately validates it again for the current request. The returned plan remains an ordinary `QueryPlan`, not an authorization token. Optional `planner_result.presentation` is structurally separate and cannot affect query execution.

## Shared query/help orchestration

For behavior closest to `/asklens/query/`, use the shared core orchestration helper. It handles data questions, capability/help questions, submitted plans, debug gating, audit records, and safe provider fallbacks without importing DRF.

```python
from django_asklens.querying import execute_asklens_query_request

response = execute_asklens_query_request(
    request,
    question="What can I query?",
    include_presentation=True,
)

if response.response_type == "capabilities":
    suggestions = response.payload["help"]["content"]["suggestions"]
elif response.response_type == "query":
    rows = response.payload["result"]["data"]
else:
    error_code = response.payload["error"]["code"]
    error_message = response.payload["error"]["message"]
```

The shared query-success payload embeds the complete existing core result under
`result`, including optional `empty: true`; adapter question, plan, audit,
presentation, explanation, and staff debug fields remain siblings. Capability/
help payloads keep exact `capabilities` and permission-scoped `catalog` children,
with adapter routing under `routing` and human guidance under `help`. These are
intentional alpha response shapes, not public contract stability.

By default, execution writes one `SemanticQueryRun` containing operational
metadata only. `question` is blank and `plan` contains only validated resource/
intent metadata; rejected raw plans are not stored. Capability/help responses do
not create query-run records because they do not execute a database query.

Audit settings are server-owned:

```python
DJANGO_ASKLENS = {
    "AUDIT_MODE": "database",  # "database", "disabled", or "custom"
    "AUDIT_INCLUDE_CONTENT": False,
    "AUDIT_DATABASE_ALIAS": None,  # or one trusted non-empty Django alias
    "AUDIT_SINK": None,  # callable/import path required for "custom"
}
```

A custom sink receives a safe operational event mapping and adds no database SQL unless the host sink chooses to do so. Disabled mode adds no audit SQL. Setting `AUDIT_INCLUDE_CONTENT=True` adds the question and complete validated plan to database/custom events; enable it only with an explicit retention, access, redaction, deletion, backup, and replica policy. Audit-sink failure is logged server-side and does not trigger rejected-plan execution or replace a successful query result.

`AUDIT_DATABASE_ALIAS=None` preserves ordinary Django database routing for built-in audit writes and run-detail reads. A configured non-empty alias is server-owned and used explicitly for both operations; HTTP/query payloads cannot select it, and failure never falls back to `default`. A malformed, missing, or unavailable alias produces normal audit-sink failure behavior for writes and a fixed `asklens.execute.failed` HTTP error envelope for run-detail reads without reflecting database diagnostics. Explicit lifecycle-command `--database` selection is independent and unchanged.

### Run-detail access and display policy

`GET /asklens/runs/<id>/` is an audit view, not an internal result or error document. Configured API permission classes run first. After that route gate, a row is fetched only through an authorization-filtered queryset: the owner may read it, and cross-user audit review requires Django's global `asklens.view_semanticqueryrun` permission. `is_staff` alone is insufficient; active superusers follow Django's normal `has_perm()` behavior. Missing and inaccessible IDs return the same opaque `404` `asklens.member.unavailable` envelope, and reads create no audit row.

The current content setting is enforced again at serialization time. Unless `AUDIT_INCLUDE_CONTENT` is exactly the boolean `True`, `question` is blank and `plan` contains only safe resource/intent operational metadata, even if a legacy or manually populated row retained more content. With explicit boolean `True`, an authorized viewer may receive the stored question and full plan; the host must then govern retention, access, redaction, deletion, backups, replicas, and every other display/export path.

The model's free-form `error` text is never returned. Failed rows expose a structured safe `{code, message}` derived from a recognized AskLens code and its canonical public message; unknown or malformed stored text becomes one fixed generic safe error. Successful rows and blank errors return `null`. Do not place private Django bindings, permission strings, tenant identifiers, credentials, rows, provider payloads, raw rejected content, or database diagnostics in audit responses or host-written audit fields.

### Manual database-audit lifecycle commands

Trusted operators can preview redaction or irreversible purge of built-in
`SemanticQueryRun` rows older than a strict aware RFC 3339 cutoff:

```bash
python manage.py redact_asklens_audit \
  --before 2026-08-01T00:00:00Z \
  --database default \
  --batch-size 1000

python manage.py purge_asklens_audit \
  --before 2026-08-01T00:00:00Z \
  --database default \
  --batch-size 1000
```

Both commands require the uppercase offset-aware cutoff, support batch sizes
from 1 through 10000, and preview by default. Preview performs a point-in-time
eligible-row count with no writes. Review that count before adding `--execute`.
Output is limited to the operation, selected alias, canonical UTC cutoff,
counts, batch size, and mode—never high-water/row IDs or stored content.

`redact_asklens_audit --execute` clears exactly `question` and `plan` in short
primary-key batches while retaining the principal reference, status, row count,
duration, error, and creation time. Its selected alias needs update permission.

`purge_asklens_audit --execute` irrevocably targets rows with
`created_at < before`. Make and test a host-appropriate backup/restore plan
first. The command captures the initially eligible maximum primary key, so
ordinary later higher-PK inserts wait for another run. Manually inserted or
reused lower PKs and concurrent changes are not covered by a snapshot guarantee.
The command uses short primary-key batch transactions and reports actual
`SemanticQueryRun` rows deleted; concurrent updates/deletes may make that count
differ from preview. The selected alias needs delete permission plus permissions
required by related-object behavior.

Purge uses normal public Django `QuerySet.delete()` behavior: `pre_delete` and
`post_delete` signals run, and configured relationships may cascade, update,
protect, restrict, or otherwise block related host rows. Each batch commits
independently. A failing batch rolls back its own database changes, but earlier
committed batches remain deleted if a later batch or signal fails. Rerun preview
and reconcile retained/deleted rows before retrying. External effects performed
by signal handlers cannot be rolled back and remain the host's responsibility.

The lifecycle command code does not resolve or invoke configured `AUDIT_SINK`
callables. Redaction only updates `question` and `plan` on selected built-in
rows. Purge targets selected `SemanticQueryRun` rows, while host delete signals
and collector relationships may perform their own effects. Custom-sink storage,
backups, and replicas remain host-owned. AskLens provides no scheduler or
automatic retention policy, and these commands are not a complete user/tenant
access or deletion-request workflow.

The packaged `SemanticQueryRun` admin is view-only. It preserves Django's
inherited view semantics, so users with the model's raw view or change
permission can open its list and detail pages, but its admin policy denies add,
change, and delete for every principal, including superusers. Django therefore
filters out bulk `delete_selected`, and forged admin mutation requests do not
change built-in audit rows. The redaction and purge commands are separate,
AskLens-provided operator workflows; they do not define universal host
authorization or prevent ORM/database mutation outside the packaged admin. Host
projects must still restrict command execution and all other storage access.

## Optional access gate helper

AskLens includes a small DRF-compatible authenticated-user gate that does not require DRF:

```python
from django_asklens.access import can_access_asklens

if not can_access_asklens(request):
    raise PermissionDenied("You do not have permission to use AskLens.")
```

The default configured gate is `django_asklens.access.IsAuthenticated`. Projects using the optional API can still configure DRF permission classes in `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]`.

## Safety boundaries

Core-only callers preserve the normal execution safety model by using `execute_plan()` with the current request. In particular:

- do not execute LLM-generated SQL;
- do not add write/update/delete query intents;
- do not auto-register every model or field;
- do not send database rows or sample values to providers by default;
- always pass the current request to execution and keep context scope providers server-owned;
- submit saved or edited plan payloads through `execute_plan()` so they are revalidated before execution.
