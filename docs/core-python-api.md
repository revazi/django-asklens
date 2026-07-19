# Core Python API

Django AskLens can be used without Django REST Framework. Install the core package when you want to register semantic resources, ask a provider for validated `QueryPlan` JSON, compile safe Django ORM queries, execute them, and serialize results from Python code.

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

If your application already has a plan payload, parse and validate it before execution. Validation checks the registered catalog, allowed fields, permissions, limits, relation depth, raw-SQL-like payloads, and read-only intent.

```python
from django_asklens.execution import run_query_plan
from django_asklens.permissions import get_request_permissions
from django_asklens.planning import parse_and_validate_query_plan

payload = {
    "resource": "orders",
    "intent": "aggregate",
    "group_by": [{"field": "status"}],
    "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
    "order_by": [{"metric": "order_count", "direction": "desc"}],
    "limit": 10,
    "visualization": {"type": "bar", "x": "status", "y": "order_count"},
}

permissions = get_request_permissions(request)
plan = parse_and_validate_query_plan(payload, permissions=permissions)
result = run_query_plan(plan, request=request)
response_payload = result.to_dict()
```

`run_query_plan(...)` always starts from the resource `base_queryset(request)` hook, so row-level scoping stays in the host project.

## Ask a provider, then execute

The planner uses the configured backend by default. The default `dummy` backend is deterministic and makes no network calls.

```python
from django_asklens.execution import run_query_plan
from django_asklens.permissions import get_request_permissions
from django_asklens.planning import plan_question

permissions = get_request_permissions(request)
planner_result = plan_question("Show orders by status", permissions=permissions)
result = run_query_plan(planner_result.plan, request=request)
payload = result.to_dict()
```

The provider result is still untrusted: `plan_question(...)` validates provider output before returning a plan. If validation fails, AskLens raises a safe AskLens exception instead of executing anything.

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
    error = response.payload["error"]
```

This helper persists `SemanticQueryRun` audit records for data-query success and safe data-query failure. Capability/help responses do not create query-run records because they do not execute a database query.

## Optional access gate helper

AskLens includes a small DRF-compatible authenticated-user gate that does not require DRF:

```python
from django_asklens.access import can_access_asklens

if not can_access_asklens(request):
    raise PermissionDenied("You do not have permission to use AskLens.")
```

The default configured gate is `django_asklens.access.IsAuthenticated`. Projects using the optional API can still configure DRF permission classes in `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]`.

## Safety boundaries

Core-only usage has the same safety model as the optional API:

- do not execute LLM-generated SQL;
- do not add write/update/delete query intents;
- do not auto-register every model or field;
- do not send database rows or sample values to providers by default;
- always pass the current request to execution when row scope depends on the user;
- always revalidate saved or edited plan payloads before execution.
