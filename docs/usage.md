# Usage guide

## 1. Register resources

AskLens only queries resources that your project explicitly registers. Register resources during app startup, such as from an app config `ready()` method or another import path you control.

```python
from django_asklens import Metric, register
from shop.models import Order

register(
    model=Order,
    name="orders",
    label="Orders",
    description="Customer orders placed in the store",
    default_date_field="created_at",
    fields={
        "id": {"label": "Order ID"},
        "status": {"label": "Status"},
        "created_at": {"label": "Created date"},
        "customer.email": {"label": "Customer email", "sensitive": True},
        "total": {"label": "Order total", "metric": True},
    },
    metrics=[
        Metric("order_count", op="count", field="id", label="Number of orders"),
        Metric("revenue", op="sum", field="total", label="Revenue"),
    ],
)
```

Sensitive fields are hidden from the default catalog serialization. Hidden fields and internal model names are not sent to the planner prompt by default.

## 2. Configure a provider

The MVP ships with `DummyProvider`, which maps exact questions to deterministic `QueryPlan` payloads. It is useful for tests, local demos, and evaluation fixtures.

```python
DJANGO_ASKLENS = {
    "LLM_BACKEND": "dummy",
    "DUMMY_PLANS": {
        "Show orders by status": {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            "order_by": [{"metric": "order_count", "direction": "desc"}],
            "limit": 100,
            "visualization": {"type": "bar", "x": "status", "y": "order_count"},
        }
    },
}
```

## 3. Discover what can be queried

Use the capabilities endpoint to show users what AskLens can answer for the current request permissions. The response is generated from permission-scoped catalog metadata only; it does not include database rows or sample values.

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
      "fields": [{"name": "status", "label": "Status", "can_group": true}],
      "metrics": [{"name": "order_count", "label": "Number of orders"}],
      "examples": ["Show count of Orders by Status"]
    }
  ]
}
```

## 4. Query through the API

```http
POST /asklens/query/
Content-Type: application/json

{"question": "Show orders by status"}
```

A successful data-query response includes the question, validated plan, column metadata, normalized rows, visualization hint, timing, and audit run id. In live mode, deciding between data query and capability help plus producing the data `QueryPlan` happens in one provider call. Advanced clients may submit a previously returned `query_help.suggestions[].plan` with the question; AskLens revalidates the plan against the current request permissions and executes it directly instead of making another LLM call.

```json
{
  "question": "Show orders by status",
  "plan": {"resource": "orders", "intent": "aggregate"},
  "columns": [{"key": "status", "label": "Status", "type": "string"}],
  "data": [{"status": "paid", "order_count": 2}],
  "visualization": {
    "type": "bar",
    "x": {"field": "status", "label": "Status", "type": "string"},
    "y": {"field": "order_count", "label": "Number Of Orders", "type": "number"}
  },
  "run_id": 1
}
```

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

Projects that want a built-in reference/demo UI can mount the dependency-free AskLens frontend. It uses the same API endpoints and Django session authentication as the rest of AskLens. Users can save useful questions locally in their browser; saved plans are sent back only as normal query requests and are revalidated against current permissions before execution.

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

## 6. Query from Python

```python
from django_asklens.llms import DummyProvider
from django_asklens.planning import plan_question
from django_asklens.execution import run_query_plan

provider = DummyProvider(plans={"Show orders by status": {...}})
planner_result = plan_question("Show orders by status", provider=provider)
result = run_query_plan(planner_result.plan)
payload = result.to_dict()
```

## Limitations

- Only list and aggregate intents are supported.
- Only registered resources, fields, and metrics are queryable.
- No raw SQL mode exists in the MVP.
- No write/update/delete actions are supported.
- Live LLM providers are opt-in; the dummy provider remains the default.
