# Django AskLens

[![PyPI](https://img.shields.io/pypi/v/django-asklens.svg)](https://pypi.org/project/django-asklens/)
[![Python](https://img.shields.io/pypi/pyversions/django-asklens.svg)](https://pypi.org/project/django-asklens/)

Django AskLens is a reusable Django package for safe natural-language querying over explicitly registered Django models, with an optional Django REST Framework API integration.

AskLens does **not** let an LLM write SQL. It asks a provider for structured JSON, validates the plan against your registered catalog and permissions, compiles a read-only Django ORM query, executes with limits, and returns table/chart-ready JSON.

Status: **alpha**. APIs may change before a stable release.

## What it provides

- Explicit semantic resource registration.
- Permission-scoped catalog metadata plus separate machine capabilities.
- Optional DRF catalog, capabilities, query, and run-detail endpoints.
- Strict Pydantic `QueryPlan` validation.
- Five packaged draft internal JSON Schemas for the current contract shape.
- A language-neutral synthetic conformance corpus replayed on SQLite and required PostgreSQL 15/18 CI jobs.
- A source-checkout PostgreSQL 18 Compose/Playwright synthetic reference smoke.
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

Register a resource during app startup. This example inherits the safe `DEFAULT_SCOPE_MODE="context_scoped"` setting shown below:

```python
from django_asklens import Metric, register
from shop.models import Order


def visible_orders(request):
    if not getattr(request.user, "is_authenticated", False):
        return Order.objects.none()
    return Order.objects.filter(account__memberships__user=request.user)


register(
    timezone="UTC",
    model=Order,
    name="orders",
    label="Orders",
    description="Orders visible to the current user.",
    default_date_field="created_at",
    fields={
        "order_id": {
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
        "customer.email": {
            "binding": "customer__email",
            "type": "string",
            "nullable": False,
            "label": "Customer email",
            "sensitive": True,
            "requires_permission": "customers.view_pii",
        },
        "total_cents": {
            "binding": "total_cents",
            "type": "integer",
            "nullable": False,
            "label": "Total in cents",
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
            binding="total_cents",
            result_type="integer",
            label="Revenue",
        ),
    ],
    default_order=(("created_at", "desc"),),
    requires_permission="orders.view_reports",
    scope_provider=visible_orders,
)
```

Field mapping keys are stable public semantic names. Each field explicitly declares its private Django `binding`, canonical `type`, and `nullable` contract; bindings use Django `__` traversal syntax and are never serialized to catalogs or providers. Every resource also declares a server-owned IANA `timezone`; there is no client or implicit Django `TIME_ZONE` fallback. Metrics own their private binding, operation, result type, permission, and relationship-cardinality policy; plans reference only the registered metric name. `requires_permission` on the resource gates catalog visibility and query validation for the whole resource. Field- and metric-level `requires_permission` gate individual members without exposing permission tokens in public metadata.

Start with the deterministic dummy provider:

```python
DJANGO_ASKLENS = {
    "DEFAULT_SCOPE_MODE": "context_scoped",
    "LLM_BACKEND": "dummy",
    "DUMMY_PLANS": {
        "Show orders by status": {
            "query_plan": {
                "resource": "orders",
                "intent": "aggregate",
                "group_by": [{"field": "status"}],
                "metrics": [{"metric": "order_count"}],
                "limit": 100,
            },
            "presentation": {
                "kind": "bar",
                "x": "status",
                "y": "order_count",
            },
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
  "columns": [
    {"key": "status", "label": "Status", "type": "string", "nullable": false},
    {
      "key": "order_count",
      "label": "Orders",
      "type": "integer",
      "nullable": false
    }
  ],
  "data": [{"status": "paid", "order_count": 12}],
  "row_count": 1,
  "result_metadata": {
    "limit": 100,
    "limit_scope": "groups",
    "truncated": false
  },
  "presentation": {"kind": "bar"}
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

- Only explicitly registered resources and fields are queryable through the normal validated orchestration paths.
- Every resource resolves to `global` or `context_scoped`. Projects may configure `DEFAULT_SCOPE_MODE="context_scoped"` once, but `global` must always be explicit per resource. Context-scoped resources require a trusted `scope_provider(request)`; omission, invalid provider results, and provider failures reject without falling back to the model manager.
- Sensitive fields are hidden unless explicitly permissioned through the normal validation paths.
- Plans are bounded before ORM compilation by UTF-8 bytes, filters, selected/order/group/metric terms, relationship depth and unique edges, `in`/total filter values, and returned rows/groups.
- List ordering uses semantic resource defaults plus a private unique row identity; grouped queries append group-key tie-breakers, nulls sort last, and `truncated` is derived by fetching one extra row/group.
- Filter operators and JSON values are checked against canonical field types before scope resolution; decimals remain strings, explicit enum aliases are server-registered, and Django choices are not auto-exposed.
- Result columns include type/nullability metadata. Empty aggregates and decimal serialization are deterministic, and unsupported runtime values fail instead of being stringified.
- Provider and submitted-plan output is untrusted and validated by the normal API, admin, and MCP orchestration before execution.
- Use `django_asklens.execution.execute_plan()` for Python execution; it revalidates mappings and existing `QueryPlan` objects for the current request. `run_query_plan()` is a deprecated wrapper that also requires the current request. The compiler and compiled-query executor are internal and are not public exports.
- AskLens executes read-only Django ORM queries only.
- AskLens does not execute LLM-generated SQL.
- AskLens does not create, update, or delete application data; its own optional/default audit sink may write one `SemanticQueryRun` metadata record per query attempt.
- Default audit records omit questions, filter values, and complete plans unless `AUDIT_INCLUDE_CONTENT=True` is explicitly configured.
- AskLens does not send database rows, sample values, secrets, credentials, or `.env` content to providers by default.
- Query runs are audited.

Review the [security checklist](docs/security-checklist.md) and [production checklist](docs/production-checklist.md) before enabling AskLens outside local development.

## Alpha scope and safety boundaries

- APIs may change before a stable release.
- This alpha is not a production-security certification. Host applications remain responsible for authentication, correct scope-provider policy, database and request timeouts, rate/concurrency limits, read-only database defense where appropriate, and application-specific security testing.
- AskLens supports read-only list and aggregate questions over explicitly registered resources.
- Query quality depends on clear resource, field, description, and metric registration.
- Live provider behavior varies by model and prompt complexity; `DummyProvider` remains the deterministic default for tests and demos.
- SQL generation/execution is intentionally out of scope. AskLens uses validated QueryPlan JSON and Django ORM compilation only.
- Writes and mutations are intentionally out of scope.
- Server-side saved queries, dashboard builders, and a dedicated help endpoint are not part of the alpha package surface.
- The packaged frontend is a reference/demo UI; custom product UIs should call the API directly.
- Read-only replica/database routing is a host-project deployment concern in alpha.
- Current package metadata and CI target Django 5.2 LTS and Django 6.x.

## Documentation

- [Installation](docs/installation.md)
- [Usage guide](docs/usage.md)
- [Migrating from 0.1 alpha to 0.2 alpha](docs/migrating-0.1-to-0.2.md)
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
- [Runnable complex test project and PostgreSQL reference smoke](docs/test-project-demo.md)
- [Changelog](CHANGELOG.md)

## Development

Use Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/) for local development. The dev dependency group includes DRF so the API integration tests run locally.

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The opt-in source-checkout PostgreSQL 18 browser smoke is:

```bash
uv run playwright install chromium
bash scripts/reference-demo-smoke.sh
```

It uses only synthetic data, disables live providers, and is internal draft alpha-candidate evidence—not production/security certification, external validation, or backend-neutral proof. The package remains standards-based and setuptools-backed; `uv`, Docker, PostgreSQL drivers, and Playwright are contributor/evidence tools, not mandatory runtime dependencies.
