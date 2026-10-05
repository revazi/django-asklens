# Django AskLens

[![PyPI](https://img.shields.io/pypi/v/django-asklens.svg)](https://pypi.org/project/django-asklens/)
[![Python](https://img.shields.io/pypi/pyversions/django-asklens.svg)](https://pypi.org/project/django-asklens/)

Django AskLens is the Django implementation of the [AskLens specification](docs/asklens-specification.md): safe natural-language querying over explicitly registered Django models, with optional Django REST Framework and MCP adapters.

AskLens does **not** let an LLM write SQL. It asks a provider for structured JSON, validates the plan against your registered catalog and permissions, compiles a read-only Django ORM query, executes with limits, and returns table/chart-ready JSON.

Status: **alpha**. The `0.3.x` line has a [narrow governed core
boundary](docs/compatibility.md); provisional adapters, documents, and helpers
may still change before a stable release.

Django AskLens was created by [Revaz Zakalashvili](https://github.com/revazi) ([revaz.zakalashvili@gmail.com](mailto:revaz.zakalashvili@gmail.com)).

## Package provenance

> [!IMPORTANT]
> `django-asklens==0.3.1` is the current published alpha, not a stable or
> production-certified release. Use its immutable
> [`v0.3.1` source snapshot](https://github.com/revazi/django-asklens/blob/v0.3.1/README.md)
> and [GitHub Release](https://github.com/revazi/django-asklens/releases/tag/v0.3.1).
> Their pre-publication wording is preserved as historical release evidence;
> this main-branch notice records the post-publication status. The annotated tag
> object is
> `34f123230c2ea09622f0f2906eeaf775619f78bb`; its release source is commit
> `1b19ba8dea81117d9ff79d64bd28e3136cd93e6e` and tree
> `5a914eb84b697d0d7c030b311d68c305df9a9ed5`.
>
> Install the exact public core, provisional API, or provisional MCP surface:
>
> ```bash
> python -m pip install 'django-asklens==0.3.1'
> python -m pip install 'django-asklens[api]==0.3.1'
> python -m pip install 'django-asklens[mcp]==0.3.1'
> ```
>
> Authenticate `django_asklens-0.3.1-py3-none-any.whl` with SHA-256
> `4332c62aad6e7b27f553af3f8796ed6090e6207ddad6a30a1c4665e9a1085887`
> or `django_asklens-0.3.1.tar.gz` with SHA-256
> `5e011f2272a7fe6f53df5bae757d045042d39e31cfba40eb51766d703eb38dde`.
> A same-version local rebuild is separate local evidence and must not be
> represented as either immutable public artifact. Package metadata requires
> Python `>=3.12` and Django `>=5.2,<7.0`; release checks cover Python 3.12/3.13
> and Django 5.2/6.0/6.1.
>
> Immutable public `0.3.0` is the immediate prior supported upgrade origin. The
> immutable `django-asklens==0.2.0` release remains the supported older `0.2.x`
> origin; use each version's matching immutable tagged documentation. The
> previously published `0.1.0a1` package was an unsupported testing artifact and
> is not an upgrade origin. See [Installation](docs/installation.md) for
> public-artifact authentication, local rebuild evidence, and bounded `0.3.x`
> upgrade guidance.

## What it provides

- The [AskLens specification](docs/asklens-specification.md): untrusted plans over an explicit catalog, with current-request authorization and row scope.
- Explicit semantic resource registration.
- Permission-scoped catalog metadata plus separate machine capabilities.
- Optional DRF catalog, capabilities, query, and run-detail endpoints.
- Strict Pydantic `QueryPlan` validation.
- Five packaged unversioned JSON Schemas for the current spec documents.
- A language-neutral synthetic conformance corpus replayed on SQLite and required PostgreSQL 15/18 CI jobs.
- A source-checkout PostgreSQL 18 Compose/Playwright synthetic reference smoke.
- ORM-only list and aggregate query execution.
- Dummy provider for deterministic tests and demos.
- OpenAI-compatible live provider adapter.
- Query-run audit records.
- Frontend-agnostic `columns` + `data` JSON output.
- Optional packaged browser UI for demos/reference use.

## 0.3.1 alpha quickstart

The example below applies to the immutable public `0.3.1` alpha. Install the
exact version and authenticate its public artifact as described above. Users
upgrading from the immediate prior `0.3.0` release or the supported older
`0.2.0` origin should follow the bounded guidance in
[Installation](docs/installation.md).

For a linear path that installs core only, wires one project-owned startup import, and executes current-request list plans, use the [Core-only executable quickstart](docs/quickstart-core.md).

For the optional DRF adapter, follow the [Authenticated normal-user API quickstart](docs/usage.md#authenticated-normal-user-api-quickstart). It installs an exact current `[api]` artifact, uses a host-created authenticated user and server-assigned permission, checks that user's permission-scoped catalog first, then demonstrates the current deterministic query, opaque denial, and metadata-only audit outcomes. If the resource is absent from the catalog, diagnose host permission assignment and the single startup registration import; do not weaken the opaque query error. AskLens uses the host's existing authentication and does not provide a login or token endpoint.

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

Successful data responses keep adapter metadata outside one complete core
`result` document:

```json
{
  "run_id": 1,
  "question": "Show orders by status",
  "response_type": "query",
  "plan": {"resource": "orders", "intent": "aggregate", "limit": 100},
  "result": {
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
    "duration_ms": 4,
    "result_metadata": {
      "limit": 100,
      "limit_scope": "groups",
      "truncated": false
    }
  },
  "presentation": {"kind": "bar"}
}
```

Help questions such as `show me example queries` return `response_type:
"capabilities"` with exact `capabilities` and permission-scoped `catalog`
children, plus separate `routing` and human `help` objects, without running a
database query.

## Building a UI

When installed with the `api` extra, AskLens is API-first. Build your own UI with React, Vue, HTMX, Django templates, a mobile client, or any chart/table library by rendering the returned `result.columns` and `result.data` arrays.

The packaged frontend is optional and intended as a dependency-free demo/reference UI. Projects that need product-specific layout, charts, saved queries, or workflows should call the API directly. See [Building a custom AskLens UI](docs/custom-ui.md).

For a concise source-checkout journey that starts with the scoped `facility-owner` identity, then separates frontend, admin query, view-only audit, safe denial, and reset steps, follow the [source demo frontend/admin first run](docs/test-project-demo.md#sqlite-frontend-and-admin-first-run-start-to-reset). It uses only synthetic data and deterministic offline help; it is not a supported upgrade path from the historical `0.1.0a1` testing artifact.

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
- The optional query API rejects unknown top-level keys—including client policy claims—before orchestration, audit, or application-data SQL without reflecting their names, values, or serializer diagnostics.
- All handled failures from the four AskLens DRF views use one `{error, run_id?}` envelope with fixed safe messages; statuses and applicable `Allow`, `WWW-Authenticate`, and `Retry-After` headers are preserved. This route-local behavior does not change unrelated host DRF endpoints.
- Use `django_asklens.execution.execute_plan()` for Python execution; it revalidates mappings and existing `QueryPlan` objects for the current request. The compiler and compiled-query executor are internal and are not public exports.
- AskLens executes read-only Django ORM queries only.
- AskLens does not execute LLM-generated SQL.
- AskLens does not create, update, or delete application data; its own optional/default audit sink may write one `SemanticQueryRun` metadata record per query attempt.
- Default audit records omit questions, filter values, and complete plans unless `AUDIT_INCLUDE_CONTENT=True` is explicitly configured; run detail reapplies that current policy even to legacy rows.
- Run detail is owner-only unless the current user has global `asklens.view_semanticqueryrun`; `is_staff` alone is insufficient, inaccessible/missing IDs share an opaque `404`, and stored free-form errors are returned only as canonical safe `{code, message}` metadata or `null`.
- Built-in audit writes and run-detail reads may use one optional server-owned `AUDIT_DATABASE_ALIAS`; clients cannot select it and a configured alias never falls back to `default`.
- Optional `OBSERVABILITY_SINK` lifecycle events are default-off, immutable, content-free, dependency-free, and scheduled only after the authoritative audit attempt. Enclosing transactions commit before callback delivery, raised callback errors do not propagate into AskLens control flow, and observability is not audit; trusted host callback side effects remain host-owned.
- AskLens does not send database rows, sample values, secrets, credentials, or `.env` content to providers by default.
- Query runs are audited; hosts own audit retention, access, redaction, deletion, backups, replicas, and any full-content policy.

Review the [security checklist](docs/security-checklist.md) and [production checklist](docs/production-checklist.md) before enabling AskLens outside local development.

## Alpha scope and safety boundaries

- Only the exact registration, execution, public-error, and observability rows in the [0.3.x compatibility boundary](docs/compatibility.md) are governed for that line. This is not a 1.0 stability claim; provisional APIs may change.
- This alpha is not a production-security certification. Host applications remain responsible for authentication, correct scope-provider policy, database and request timeouts, rate/concurrency limits, read-only database defense where appropriate, and application-specific security testing.
- AskLens supports read-only list and aggregate questions over explicitly registered resources.
- Query quality depends on clear resource, field, description, and metric registration.
- Live provider behavior varies by model and prompt complexity; `DummyProvider` remains the deterministic default for tests and demos.
- SQL generation/execution is intentionally out of scope. AskLens uses validated QueryPlan JSON and Django ORM compilation only.
- Writes and mutations are intentionally out of scope.
- Server-side saved queries, dashboard builders, and a dedicated help endpoint are not part of the alpha package surface.
- The packaged frontend is a reference/demo UI; custom product UIs should call the API directly.
- Read-only replica/database routing is a host-project deployment concern in alpha.
- Installation metadata remains `Django>=5.2,<7.0`, but current CI support evidence is deliberately limited to Django 5.2 LTS, 6.0, and 6.1.

## Documentation

- [Installation](docs/installation.md)
- [0.3.x compatibility boundary](docs/compatibility.md)
- [Host observability controls](docs/host-throttle-and-audit-controls.md)
- [Release process](docs/releasing.md)
- [0.3.x maintenance roadmap](docs/maintenance-roadmap.md)
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
- [Example Django AskLens integration](docs/test-project-demo.md)
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

It uses only synthetic data, disables live providers, and is internal alpha release-source evidence—not production/security certification, external validation, or backend-neutral proof. The package remains standards-based and setuptools-backed; `uv`, Docker, PostgreSQL drivers, and Playwright are contributor/evidence tools, not mandatory runtime dependencies.
