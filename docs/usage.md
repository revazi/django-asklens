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

A response includes visible resources, exposed fields, metrics, date fields, example questions, supported patterns, and limitations. Users can also ask capability/help questions through `/asklens/query/`; live/custom providers classify those semantically with a strict `QuestionIntent` schema, then generate suggested AskLens questions with a strict `QueryHelp` schema using only the visible capabilities metadata. Dummy/offline mode uses deterministic examples for obvious help questions such as `What can I query?`.

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

A successful data-query response includes the question, validated plan, column metadata, normalized rows, visualization hint, timing, and audit run id.

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

Capability/help questions return a non-row response and do not execute a database query. In live mode, `query_help_source` is `semantic_provider` when suggestions came from the configured LLM and passed catalog-reference validation:

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
      {"question": "Show count of Orders by Status", "resource_name": "orders"}
    ]
  }
}
```

## 5. Query from Python

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
