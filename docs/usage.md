# Usage guide

## 1. Register resources

AskLens only queries resources that your project explicitly registers. Register resources during app startup, such as from an app config `ready()` method or another import path you control. Projects whose resources are normally request-scoped can configure the safe default once:

```python
DJANGO_ASKLENS = {
    "DEFAULT_SCOPE_MODE": "context_scoped",
}
```

```python
from django_asklens import Metric, register
from shop.models import Order


def visible_orders(request):
    if not getattr(request.user, "is_authenticated", False):
        return Order.objects.none()
    return Order.objects.filter(account__memberships__user=request.user)


register(
    model=Order,
    name="orders",
    label="Orders",
    description="Customer orders placed in the store",
    default_date_field="created_at",
    fields={
        "id": {
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
        "customer.email": {
            "binding": "customer__email",
            "type": "string",
            "nullable": False,
            "label": "Customer email",
            "sensitive": True,
            "requires_permission": "customers.view_pii",
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
            label="Number of orders",
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

Resource-level `requires_permission` gates the whole resource. Field- and metric-level `requires_permission` gate individual members. Sensitive fields are hidden from the default catalog serialization. Private Django bindings, metric operations, distinct keys, permission tokens, hidden fields, and internal model names are never sent to the planner prompt. Field mapping keys and metric names are public semantics; they are not translated into ORM paths.

Every resource must resolve to `global` or `context_scoped`. `DEFAULT_SCOPE_MODE` can only be `context_scoped`; global resources must declare `scope_mode="global"` individually. Context-scoped resources require a trusted `scope_provider`; missing or invalid scope never falls back to the default manager.

## 2. Configure a provider

AskLens ships with `DummyProvider`, which maps exact questions to deterministic `QueryPlan` payloads. It is useful for tests, local demos, and evaluation fixtures.

```python
DJANGO_ASKLENS = {
    "DEFAULT_SCOPE_MODE": "context_scoped",
    "LLM_BACKEND": "dummy",
    "DUMMY_PLANS": {
        "Show orders by status": {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"metric": "order_count"}],
            "order_by": [{"metric": "order_count", "direction": "desc"}],
            "limit": 100,
            "visualization": {"type": "bar", "x": "status", "y": "order_count"},
        }
    },
}
```

## 3. Discover what can be queried

With the optional `api` extra installed, use the capabilities endpoint to show users what AskLens can answer for the current request permissions. The response is generated from permission-scoped catalog metadata only; it does not include database rows or sample values.

```http
GET /asklens/capabilities/
```

A response includes visible resources, exposed fields, metrics, date fields, example questions, supported patterns, and limitations. Users can also ask capability/help questions through `/asklens/query/`. In live mode, AskLens uses one unified provider call to decide whether the request is a data query or capability help, using visible capabilities metadata once. Provider-backed suggestions include catalog references, and AskLens synthesizes/validates executable QueryPlans from those references locally before returning help. Dummy/offline mode uses deterministic examples for obvious help questions such as `What can I query?`.

```json
{
  "summary": "You can ask read-only list and aggregate questions over 1 resource.",
  "resources": [
    {
      "name": "orders",
      "label": "Orders",
      "fields": [
        {
          "name": "status",
          "label": "Status",
          "type": "enum",
          "can_group": true,
          "operators": ["eq", "neq", "in", "isnull"]
        }
      ],
      "metrics": [
        {"name": "order_count", "label": "Number of orders", "result_type": "integer"}
      ],
      "examples": ["Show Number of orders by Status"]
    }
  ]
}
```

## 4. Query through the optional API

```http
POST /asklens/query/
Content-Type: application/json

{"question": "Show orders by status"}
```

A successful data-query response includes `response_type: "query"`, the question, validated plan, column metadata, normalized rows, limit metadata, visualization hint, timing, and audit run id. In live mode, deciding between data query and capability help plus producing the data `QueryPlan` happens in one provider call. Advanced clients may submit a previously returned `query_help.suggestions[].plan` with the question; AskLens revalidates the plan against the current request permissions and executes it directly instead of making another LLM call.

```json
{
  "question": "Show orders by status",
  "response_type": "query",
  "plan": {"resource": "orders", "intent": "aggregate", "limit": 10},
  "columns": [
    {"key": "status", "label": "Status", "type": "enum", "nullable": false},
    {
      "key": "order_count",
      "label": "Number Of Orders",
      "type": "integer",
      "nullable": false
    }
  ],
  "data": [{"status": "paid", "order_count": 2}],
  "result_metadata": {
    "limit": 10,
    "limit_scope": "groups",
    "truncated": false
  },
  "visualization": {
    "type": "bar",
    "x": {"field": "status", "label": "Status", "type": "enum"},
    "y": {"field": "order_count", "label": "Number Of Orders", "type": "integer"}
  },
  "run_id": 1
}
```

For grouped aggregate/chart responses, `limit` caps returned groups/slices; for list responses it caps returned rows. AskLens fetches `limit + 1` internally and returns at most `limit`, so `result_metadata.truncated` is true only when another matching row/group exists. Ungrouped aggregates have effective limit one and always report `truncated: false`. On an empty scope they still return one row: count metrics are `0` and sum/average/minimum/maximum metrics are `null`; empty grouped aggregates return no rows. This metadata is accurate truncation detection, not cursor pagination.

Column metadata includes canonical `type` and `nullable`. Decimal values are JSON strings, floats are JSON numbers, and unknown runtime objects are rejected rather than stringified. See [Registration](registration.md) for the per-type operator matrix and explicit enum aliases.

Capability/help questions return a non-row response and do not execute a database query. In live mode, `query_help_source` is `semantic_provider` when the unified provider response chose capability help and suggestions passed catalog-reference plus locally synthesized plan validation:

```json
{
  "question": "What can I query?",
  "response_type": "capabilities",
  "routing_source": "fallback",
  "query_help_source": "deterministic",
  "capabilities": {"summary": "You can ask read-only list and aggregate questions over 1 resource."},
  "query_help": {
    "answer": "You can ask read-only list and aggregate questions over 1 resource.",
    "suggestions": [
      {
        "question": "Show count of Orders by Status",
        "resource_name": "orders",
        "plan": {"resource": "orders", "intent": "aggregate"}
      }
    ]
  }
}
```

## 5. Optional packaged frontend

Projects that want full control over layout, tables, charts, or saved-query UX can build a custom UI directly on the AskLens API; see [Building a custom AskLens UI](custom-ui.md).

Projects that want a built-in reference/demo UI can install the `api` extra and mount the dependency-free AskLens frontend. It uses the same API endpoints and Django session authentication as the rest of AskLens. Users can save useful questions locally in their browser; saved plans are sent back only as normal query requests and are revalidated against current permissions before execution.

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
    path("", include("django_asklens.frontend.urls")),  # /asklens/ui/
]
```

By default the frontend requires an authenticated Django user. To restrict it to selected users, configure a project-specific permission check:

```python
DJANGO_ASKLENS = {
    "FRONTEND_PERMISSION_CHECK": "myapp.permissions.can_use_asklens_frontend",
}
```

The callable receives the Django request and must return `True` or `False`. API route permissions still apply to `/asklens/catalog/`, `/asklens/capabilities/`, `/asklens/query/`, and `/asklens/runs/<id>/`; the frontend permission check only controls whether the packaged UI page can load.

```python
def can_use_asklens_frontend(request):
    return request.user.is_staff and request.user.has_perm("reports.view_analytics")
```

Optional frontend settings:

```python
DJANGO_ASKLENS = {
    "FRONTEND_TITLE": "Company Analytics",
    "FRONTEND_SUBTITLE": "Ask read-only questions over approved reporting data.",
    "FRONTEND_STARTER_QUESTIONS": [
        "Show orders by status",
        "Trend revenue by month",
    ],
}
```

## 6. Alpha API and product contract

For alpha, `/asklens/query/` is the single query/help entry point when the optional API integration is installed.

- In live provider mode, `/asklens/query/` makes one unified provider call that chooses either a data `QueryPlan` or capability/help suggestions.
- In dummy/offline mode, obvious help questions are handled deterministically and data questions use configured dummy plans.
- Successful data responses return `response_type: "query"`.
- Help/capability responses return `response_type: "capabilities"` and do not execute a database query.
- AskLens does not expose a separate `/asklens/help/` endpoint in alpha. Clients should use `/asklens/capabilities/` for static guidance and `/asklens/query/` for natural-language help questions.

Submitted plans are always revalidated. This applies to clicked suggestions, browser-saved plans, project-owned saved queries, and custom UI controls that modify filters, dates, ordering, or limits. A submitted plan is a latency/UX optimization, not a trust boundary or permission bypass.

Server-side saved queries are out of scope for the package alpha. Projects may store their own saved-query records, but should submit saved plans back to `/asklens/query/` so AskLens can revalidate them for the current request before execution.

The packaged frontend is a reference/demo UI for teams that want a zero-dependency starting point. It is not intended to be the supported product shell for every application. Production product experiences should generally build a custom UI on the AskLens API.

The admin query page remains available in alpha as a staff/operator utility and demo surface. It uses the same shared query/help orchestration as `/asklens/query/`; data questions create audit records, while help responses do not query the database or create query-run audit rows. It is not a replacement for a product-specific end-user UI.

## 7. Query from Python

Core Python usage does not require DRF. See the [Core Python API](core-python-api.md) guide for core-only setup, permission-scoped capabilities, plan validation, execution, result serialization, and the shared query/help orchestration helper.

```python
from django_asklens.execution import execute_plan
from django_asklens.permissions import get_request_permissions
from django_asklens.planning import plan_question

permissions = get_request_permissions(request)
planner_result = plan_question("Show orders by status", permissions=permissions)
result = execute_plan(planner_result.plan, request=request)
payload = result.to_dict()
```

`execute_plan()` treats the returned `QueryPlan` as untrusted and validates it again for the current request. Do not treat planner, saved, or edited plans as authorization tokens. See the [Core Python API](core-python-api.md) trust-boundary guidance.

## Supported alpha scope

- AskLens supports read-only list and aggregate intents.
- Only registered resources, fields, and metrics are queryable.
- List responses are capped by `MAX_ROWS`; use filters, ordering, and explicit limits to narrow large result sets.
- SQL generation/execution is intentionally out of scope; AskLens compiles validated QueryPlan JSON to Django ORM queries only.
- Write/update/delete actions are intentionally out of scope.
- Live LLM providers are opt-in; the dummy provider remains the default.
