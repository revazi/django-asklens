# Django AskLens

Django AskLens is a reusable Django + DRF package for safe natural-language querying over explicitly registered Django models.

Status: pre-alpha. The current package includes the minimal app scaffold, semantic catalog registration, strict QueryPlan schema/validation, ORM-only query compilation/execution, and a deterministic planner/provider layer. Live LLM adapters, DRF APIs, renderers, and audit models will be added in later approved phases.

## Planned names

- GitHub repository: `django-asklens`
- Python package distribution: `django-asklens`
- Python import package: `django_asklens`
- Django app label: `asklens`

## Current catalog usage

```python
from django_asklens import Metric, register
from shop.models import Order

register(
    model=Order,
    label="Orders",
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

Only explicitly registered fields are included in the semantic catalog. Sensitive, hidden, and internal Django metadata are excluded from default catalog serialization.

## Current QueryPlan validation

```python
from django_asklens.planning import parse_and_validate_query_plan

validated_plan = parse_and_validate_query_plan(
    {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
        "limit": 100,
        "visualization": {"type": "bar", "x": "status", "y": "order_count"},
    }
)
```

LLM/provider output is treated as untrusted input: it must parse as a strict QueryPlan and validate against the semantic catalog before it can be compiled or executed.

## Current ORM execution

```python
from django_asklens.execution import run_query_plan

result = run_query_plan(validated_plan)

print(result.to_dict()["data"])
```

The compiler uses Django ORM querysets only and starts from each resource's `base_queryset(request)` hook.

## Current planner/provider layer

```python
from django_asklens.llms import DummyProvider
from django_asklens.planning import plan_question

provider = DummyProvider(
    plans={
        "Show orders by status": {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            "limit": 100,
            "visualization": {"type": "bar", "x": "status", "y": "order_count"},
        }
    }
)
planner_result = plan_question("Show orders by status", provider=provider)
```

The planner sends safe catalog metadata and the strict QueryPlan JSON schema to the provider. Provider output is always parsed and validated before it can be compiled or executed.

## Safety posture

- No arbitrary SQL execution in the MVP.
- No data mutation features in the MVP.
- No sample database rows sent to LLM providers by default.
- Only explicitly registered models/resources will be queryable.

## Development

Use Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/) for local development.

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The package remains standards-based and setuptools-backed; `uv` is used for contributor workflows, not as a runtime dependency.
