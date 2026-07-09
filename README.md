# Django AskLens

Django AskLens is a reusable Django + DRF package for safe natural-language querying over explicitly registered Django models.

Status: pre-alpha. The current package includes the minimal app scaffold, semantic catalog registration, strict QueryPlan schema/validation, ORM-only query compilation/execution, deterministic and OpenAI-compatible provider layers, JSON-safe result serialization with optional visualization hints, DRF endpoints, query-run audit records, and multi-tenant security tests. Dashboards/saved queries may be added in later approved phases.

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

## Current DRF API

Include the AskLens URLs in your project URL configuration:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

Available endpoints:

```text
GET  /asklens/catalog/
POST /asklens/query/
GET  /asklens/runs/<id>/
```

The query endpoint plans, validates, executes, and records a `SemanticQueryRun` audit row. API views require authenticated users by default, and `debug=true` is restricted to staff users.

## Result serialization

AskLens returns frontend-agnostic `columns` and `data` payloads plus optional visualization hints. It does not require or own a JavaScript charting framework.

```python
from django_asklens.results import serialize_query_result

payload = serialize_query_result(
    columns=result.columns,
    rows=result.rows,
    visualization={"type": "bar", "x": "status", "y": "order_count"},
)
```

Supported visualization hints are `table`, `metric`, `bar`, `line`, and `pie`. Hints are normalized to include axis field, label, and type metadata so applications can render the returned data however they prefer. API clients that only want serialized data can send `"include_visualization": false` to `/asklens/query/`.

## Safety posture

- No arbitrary SQL execution in the MVP.
- No data mutation features in the MVP.
- No sample database rows sent to LLM providers by default.
- Only explicitly registered models/resources will be queryable.

## Documentation

- [Installation](docs/installation.md)
- [Usage guide](docs/usage.md)
- [Registration API](docs/registration.md)
- [Provider configuration](docs/providers.md)
- [Security checklist](docs/security-checklist.md)
- [Multi-tenant security](docs/multitenancy-security.md)
- [Evaluation fixtures](docs/evaluation.md)
- [Private real-project integration](docs/private-integration.md)
- [Private evaluation plan](docs/private-evaluation-plan.md)
- [Test matrix plan](docs/test-matrix.md)
- [Changelog](CHANGELOG.md)

## Development

Use Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/) for local development.

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The package remains standards-based and setuptools-backed; `uv` is used for contributor workflows, not as a runtime dependency.
