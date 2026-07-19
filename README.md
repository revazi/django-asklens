# Django AskLens

[![PyPI](https://img.shields.io/pypi/v/django-asklens.svg)](https://pypi.org/project/django-asklens/)
[![Python](https://img.shields.io/pypi/pyversions/django-asklens.svg)](https://pypi.org/project/django-asklens/)

Django AskLens is a reusable Django package for safe natural-language querying over explicitly registered Django models, with an optional Django REST Framework API integration.

AskLens does **not** let an LLM write SQL. It asks a provider for structured JSON, validates the plan against your registered catalog and permissions, compiles a read-only Django ORM query, executes with limits, and returns table/chart-ready JSON.

Status: **alpha**. APIs may change before a stable release.

## What it provides

- Explicit semantic resource registration.
- Permission-scoped catalog and capabilities metadata.
- Optional DRF catalog, capabilities, query, and run-detail endpoints.
- Strict Pydantic `QueryPlan` validation.
- ORM-only list and aggregate query execution.
- Dummy provider for deterministic tests and demos.
- OpenAI-compatible live provider adapter.
- Query-run audit records.
- Frontend-agnostic `columns` + `data` JSON output.
- Optional packaged browser UI for demos/reference use.

## Quickstart

Install from [PyPI](https://pypi.org/project/django-asklens/):

```bash
python -m pip install 'django-asklens[api]'
```

Add DRF and the AskLens app:

```python
INSTALLED_APPS = [
    # ...
    "rest_framework",
    "django_asklens",
]
```

Mount the API:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

Run migrations for AskLens audit records:

```bash
python -m django migrate asklens
```

Register a resource during app startup:

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
    description="Orders visible to the current user.",
    default_date_field="created_at",
    fields={
        "id": {"label": "Order ID"},
        "status": {"label": "Status"},
        "created_at": {"label": "Created date"},
        "customer.email": {
            "label": "Customer email",
            "sensitive": True,
            "requires_permission": "customers.view_pii",
        },
        "total_cents": {"label": "Total in cents"},
    },
    metrics=[
        Metric("order_count", op="count", field="id", label="Orders"),
        Metric("revenue", op="sum", field="total_cents", label="Revenue"),
    ],
    requires_permission="orders.view_reports",
    base_queryset=visible_orders,
)
```

`requires_permission` on the resource gates catalog visibility and query validation for the whole resource. Field-level `requires_permission` gates individual fields such as PII.

Start with the deterministic dummy provider:

```python
DJANGO_ASKLENS = {
    "LLM_BACKEND": "dummy",
    "DUMMY_PLANS": {
        "Show orders by status": {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            "limit": 100,
            "visualization": {"type": "bar", "x": "status", "y": "order_count"},
        }
    },
}
```

Ask through the API:

```http
POST /asklens/query/
Content-Type: application/json

{"question": "Show orders by status"}
```

Successful data responses include:

```json
{
  "run_id": 1,
  "question": "Show orders by status",
  "response_type": "query",
  "plan": {"resource": "orders", "intent": "aggregate", "limit": 100},
  "columns": [{"key": "status", "label": "Status", "type": "string"}],
  "data": [{"status": "paid", "order_count": 12}],
  "row_count": 1,
  "result_metadata": {
    "limit": 100,
    "limit_scope": "groups",
    "limit_reached": false
  },
  "visualization": {"type": "bar"}
}
```

Help questions such as `show me example queries` return `response_type: "capabilities"` with suggestions instead of running a database query.

## Building a UI

When installed with the `api` extra, AskLens is API-first. Build your own UI with React, Vue, HTMX, Django templates, a mobile client, or any chart/table library by rendering the returned `columns` and `data` arrays.

The packaged frontend is optional and intended as a dependency-free demo/reference UI. Projects that need product-specific layout, charts, saved queries, or workflows should call the API directly. See [Building a custom AskLens UI](docs/custom-ui.md).

## Optional packaged frontend

If you want the built-in reference UI, install the `api` extra and mount both API and frontend URLs:

```python
urlpatterns = [
    path("", include("django_asklens.api.urls")),
    path("", include("django_asklens.frontend.urls")),  # /asklens/ui/
]
```

Gate the page for selected users with:

```python
DJANGO_ASKLENS = {
    "FRONTEND_PERMISSION_CHECK": "myapp.permissions.can_use_asklens_frontend",
}
```

API route permissions still apply to every API call. The frontend permission check only controls whether the packaged page can load.

## Live providers

The default backend is `dummy` and makes no network calls. To use an OpenAI-compatible provider:

```python
import os

DJANGO_ASKLENS = {
    "LLM_BACKEND": "openai_compatible",
    "LLM_BASE_URL": "https://api.openai.com/v1",
    "LLM_API_KEY": os.environ["OPENAI_API_KEY"],
    "LLM_MODEL": "gpt-4.1-mini",
    "LLM_TEMPERATURE": 0,
}
```

Gemini can be used through its OpenAI-compatible endpoint:

```python
DJANGO_ASKLENS = {
    "LLM_BACKEND": "openai_compatible",
    "LLM_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
    "LLM_API_KEY": os.environ["GEMINI_API_KEY"],
    "LLM_MODEL": "gemini-2.5-flash",
    "LLM_TEMPERATURE": 0,
}
```

Live provider tests are opt-in and skipped by default. See [Provider configuration](docs/providers.md).

## Safety posture

- Only explicitly registered resources and fields are queryable.
- Every query starts from the resource `base_queryset(request)` hook.
- Sensitive fields are hidden unless explicitly permissioned.
- Provider output is untrusted and always validated before execution.
- AskLens executes read-only Django ORM queries only.
- AskLens does not execute LLM-generated SQL.
- AskLens does not create, update, or delete application data.
- AskLens does not send database rows, sample values, secrets, credentials, or `.env` content to providers by default.
- Query runs are audited.

Review the [security checklist](docs/security-checklist.md) and [production checklist](docs/production-checklist.md) before enabling AskLens outside local development.

## Alpha scope and safety boundaries

- APIs may change before a stable release.
- AskLens supports read-only list and aggregate questions over explicitly registered resources.
- Query quality depends on clear resource, field, description, and metric registration.
- Live provider behavior varies by model and prompt complexity; `DummyProvider` remains the deterministic default for tests and demos.
- SQL generation/execution is intentionally out of scope. AskLens uses validated QueryPlan JSON and Django ORM compilation only.
- Writes and mutations are intentionally out of scope.
- Server-side saved queries, dashboard builders, and a dedicated help endpoint are not part of the alpha package surface.
- The packaged frontend is a reference/demo UI; custom product UIs should call the API directly.
- Read-only replica/database routing is a host-project deployment concern in alpha.
- Current package metadata and CI target Django 6.x.

## Documentation

- [Installation](docs/installation.md)
- [Usage guide](docs/usage.md)
- [Core Python API](docs/core-python-api.md)
- [Custom UI guide](docs/custom-ui.md)
- [Registration API](docs/registration.md)
- [Provider configuration](docs/providers.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Security checklist](docs/security-checklist.md)
- [Production checklist](docs/production-checklist.md)
- [Multi-tenant security](docs/multitenancy-security.md)
- [Evaluation fixtures](docs/evaluation.md)
- [Runnable complex test project](docs/test-project-demo.md)
- [Changelog](CHANGELOG.md)

## Development

Use Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/) for local development. The dev dependency group includes DRF so the API integration tests run locally.

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The package remains standards-based and setuptools-backed; `uv` is used for contributor workflows, not as a runtime dependency.
