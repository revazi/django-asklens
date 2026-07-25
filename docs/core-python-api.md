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

Register only reviewed models and fields. Use `base_queryset(request)` to enforce tenant and row-level scope.

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
        "id": {"label": "Order ID"},
        "status": {"label": "Status"},
        "created_at": {"label": "Created date"},
        "total": {"label": "Order total"},
        "customer.email": {
            "label": "Customer email",
            "sensitive": True,
            "requires_permission": "customers.view_pii",
        },
    },
    metrics=[
        Metric("order_count", op="count", field="id", label="Orders"),
        Metric("revenue", op="sum", field="total", label="Revenue"),
    ],
    requires_permission="orders.view_reports",
    base_queryset=visible_orders,
)
```

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
    "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
    "order_by": [{"metric": "order_count", "direction": "desc"}],
    "limit": 10,
    "visualization": {"type": "bar", "x": "status", "y": "order_count"},
}

result = execute_plan(payload, request=request)
response_payload = result.to_dict()
```

`execute_plan(...)` repeats current semantic validation and then starts from `resource.get_base_queryset(request)`. Scope declaration is not yet fail-closed: a registered `base_queryset(request)` hook is used when present, while omission currently falls back to the model default manager. Tenant- or row-sensitive resources must register and test a scope hook until the R2 scope migration is implemented.

### Migrating low-level alpha imports

Replace `from django_asklens.compiler import compile_query_plan` and `from django_asklens.execution import execute_query` with `execute_plan()`. `CompiledQuery` is also internal. AskLens intentionally provides no public operation that executes a caller-supplied compiled or merely shape-valid plan. `run_query_plan()` remains available for one alpha cycle, emits `DeprecationWarning`, and revalidates its input.

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
- always pass the current request to execution when row scope depends on the user;
- submit saved or edited plan payloads through `execute_plan()` so they are revalidated before execution.
