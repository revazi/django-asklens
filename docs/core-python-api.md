# Core Python API

Django AskLens can be used without Django REST Framework. Install the core package when you want to register semantic resources, ask a provider for catalog-validated `QueryPlan` JSON, execute read-only Django ORM queries, and serialize results from Python code.

> **Alpha trust-boundary warning:** `parse_query_plan()` establishes structure only. Use `execute_plan(plan, request=request)` for execution: it treats mappings and existing `QueryPlan` objects as untrusted and repeats current catalog, permission, limit, and request-scope validation. `run_query_plan()` remains temporarily as a deprecated safe wrapper. The compiler and compiled-query executor are internal and no longer public exports. Never treat a previously validated `QueryPlan` as a reusable authorization token.

```bash
python -m pip install django-asklens
```

Install `django-asklens[api]` only when you want the built-in DRF routes under `django_asklens.api` or the packaged reference frontend.

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

The field mapping key is the public semantic name used by plans. `binding` is trusted server-owned Django metadata, uses `__` for relationships, and is excluded from catalog, capability, and provider payloads. `type` and `nullable` are explicit public semantics rather than values inferred from the binding. Metric operation, binding, result type, permission, distinctness, and cardinality are also trusted registration metadata; untrusted plans contain only `{"metric": "registered_name"}`.

Validation enforces the capability-declared operator matrix and canonical JSON values before scope resolution. Decimal filter values are finite strings, floats are finite JSON numbers, UUIDs normalize canonically, and `eq`/`neq` never accept null. Choice labels are not inferred from Django model metadata; use an explicit `type="enum"` definition with registered canonical values and aliases when closed-set semantics are intended. See [Registration](registration.md).

## Build permission-scoped capabilities

Use capabilities when a Python caller needs to show what the current request can query without exposing database rows or sample values.

```python
from django_asklens.catalog.capabilities import build_capabilities
from django_asklens.permissions import get_request_permissions

permissions = get_request_permissions(request)
capabilities = build_capabilities(permissions=permissions)
```

By default, AskLens reads `request.user.get_all_permissions()` for authenticated users. Projects with role, tenant, or staff-grant systems can configure `DJANGO_ASKLENS["REQUEST_PERMISSIONS_GETTER"]`.

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
    "visualization": {"type": "bar", "x": "status", "y": "order_count"},
}

result = execute_plan(payload, request=request)
response_payload = result.to_dict()
```

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

Do not infer truncation from `row_count == plan.limit` or the old `build_result_metadata(plan=..., row_count=...)` helper shape. Consume the trusted `result_metadata` returned by `QueryResult.to_dict()` or the API/MCP response.

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

AskLens query-plan failures in the API and MCP helpers use the same `error` object with `code`, safe `message`, and an optional safe JSON `pointer`. Invalid `/asklens/query/` request bodies use `asklens.parse.invalid`; transport-level authentication failures may still use the host framework's response shape. Unknown and unauthorized resources, fields, and metrics deliberately return the same `asklens.member.unavailable` response.

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
```

The provider result is still untrusted: `plan_question(...)` validates provider output before returning a plan, and `execute_plan(...)` deliberately validates it again for the current request. The returned object remains an ordinary `QueryPlan`, not an authorization token.

## Shared query/help orchestration

For behavior closest to `/asklens/query/`, use the shared core orchestration helper. It handles data questions, capability/help questions, submitted plans, debug gating, audit records, and safe provider fallbacks without importing DRF.

```python
from django_asklens.querying import execute_asklens_query_request

response = execute_asklens_query_request(
    request,
    question="What can I query?",
    include_visualization=True,
)

if response.response_type == "capabilities":
    suggestions = response.payload["query_help"]["suggestions"]
elif response.response_type == "query":
    rows = response.payload["data"]
else:
    error_code = response.payload["error"]["code"]
    error_message = response.payload["error"]["message"]
```

By default, execution writes one `SemanticQueryRun` containing operational metadata only. `question` is blank and `plan` contains only validated resource/intent metadata; rejected raw plans are not stored. Capability/help responses do not create query-run records because they do not execute a database query.

Audit settings are server-owned:

```python
DJANGO_ASKLENS = {
    "AUDIT_MODE": "database",  # "database", "disabled", or "custom"
    "AUDIT_INCLUDE_CONTENT": False,
    "AUDIT_SINK": None,  # callable/import path required for "custom"
}
```

A custom sink receives a safe operational event mapping and adds no database SQL unless the host sink chooses to do so. Disabled mode adds no audit SQL. Setting `AUDIT_INCLUDE_CONTENT=True` adds the question and complete validated plan to database/custom events; enable it only with an explicit retention, access, redaction, and deletion policy. Audit-sink failure is logged server-side and does not trigger rejected-plan execution or replace a successful query result.

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
