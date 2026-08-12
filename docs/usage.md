# Usage guide

## Authenticated normal-user API quickstart

> [!IMPORTANT]
> This journey describes the optional API in unreleased current source or a separately verified exact candidate. It is not the published PyPI `0.1.0a1`, an upgrade, a release, or a frozen API contract. Use the immutable tagged documentation for the published alpha.

This path uses Django's existing session authentication, one normal user, a host-created Django permission, a permission-scoped catalog, deterministic `DummyProvider`, and the current metadata-only database audit. AskLens does not create a login view, authentication backend, or token endpoint and does not accept identity, permission, or scope claims from the client.

### 1. Install and mount the current optional API

Install an exact current artifact with its `[api]` extra only after verifying its commit, filename, and SHA-256 digest. See [Installation](installation.md#authenticated-api-prerequisites-for-exact-current-artifacts). Add the normal host auth/session apps and middleware, `rest_framework`, AskLens, and the one host app that owns registration:

```python
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "django_asklens",
    "shop.apps.ShopConfig",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
```

Mount the API under the current documented paths:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

Run all normal host and AskLens migrations so session authentication, model permissions, and audit records are available:

```bash
python manage.py migrate
python manage.py check
```

The default AskLens route permission requires an authenticated user. Keep your host's existing login/session flow; do not treat a username, permission string, user ID, tenant ID, or scope token in an API payload as trusted.

### 2. Register one context-scoped resource once

Put the registration in one project-owned module. This example assumes `Order` has the shown account membership relation; adapt the trusted queryset to the host's own policy:

```python
# shop/asklens_registration.py
from django_asklens import register

from .models import Order

ORDER_REPORT_PERMISSION = "shop.view_order"


def visible_orders(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return Order.objects.none()
    return Order.objects.filter(account__memberships__user=user)


register(
    timezone="UTC",
    model=Order,
    name="orders",
    label="Orders",
    description="Orders visible to the current user.",
    fields={
        "status": {
            "binding": "status",
            "type": "string",
            "nullable": False,
            "label": "Status",
        },
    },
    default_order=(("status", "asc"),),
    requires_permission=ORDER_REPORT_PERMISSION,
    scope_mode="context_scoped",
    scope_provider=visible_orders,
)
```

Import only that module from the host app's `AppConfig.ready()` method:

```python
# shop/apps.py
from django.apps import AppConfig


class ShopConfig(AppConfig):
    name = "shop"

    def ready(self):
        from . import asklens_registration  # noqa: F401
```

AskLens does not autodiscover host resources. Do not also import this registration from URLs, models, admin modules, or another `AppConfig`; duplicate/autoreloader-unsafe paths fail rather than broadening access.

Configure one deterministic offline plan and metadata-only database audit:

```python
DJANGO_ASKLENS = {
    "LLM_BACKEND": "dummy",
    "DUMMY_PLANS": {
        "List my order statuses": {
            "query_plan": {
                "resource": "orders",
                "intent": "list",
                "select": ["status"],
                "order_by": [{"field": "status", "direction": "asc"}],
                "limit": 20,
            },
            "presentation": {"kind": "table"},
        }
    },
    "AUDIT_MODE": "database",
    "AUDIT_INCLUDE_CONTENT": False,
}
```

The resource permission and scope identity are server-owned. The host-code `requires_permission` token is necessarily visible to trusted developers, but it must not appear in API, catalog, or audit responses. Public semantic field names do not expose their private Django bindings.

### 3. Create and authorize a normal host user

Use the host's normal account lifecycle. For a local synthetic verification, create a non-staff/non-superuser account and assign the existing Django model permission server-side after migrations:

```python
# python manage.py shell
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

User = get_user_model()
user, _ = User.objects.get_or_create(username="asklens-reader")
user.is_staff = False
user.is_superuser = False
user.set_unusable_password()  # local verification uses force_login below
user.save()
permission = Permission.objects.get(
    content_type__app_label="shop",
    codename="view_order",
)
user.user_permissions.add(permission)
```

The permission name above is trusted host setup, not an HTTP input or output. Refresh the user/request after changing permissions so Django's permission cache cannot make a local check stale. Real users authenticate through the host's existing login flow; this quickstart does not promise or add another authentication backend.

### 4. Verify the permission-scoped catalog first

Before querying, use the same current authenticated identity to fetch `GET /asklens/catalog/`. The following Django test-client check exercises normal session middleware without creating an AskLens login endpoint:

```python
from django.contrib.auth import get_user_model
from django.test import Client

user = get_user_model().objects.get(username="asklens-reader")
client = Client()
client.force_login(user)
response = client.get("/asklens/catalog/")
assert response.status_code == 200
catalog = response.json()
assert [item["name"] for item in catalog["resources"]] == ["orders"]
assert [item["name"] for item in catalog["resources"][0]["fields"]] == ["status"]
```

An abbreviated current response is:

```json
{
  "resources": [
    {
      "name": "orders",
      "label": "Orders",
      "timezone": "UTC",
      "fields": [
        {"name": "status", "label": "Status", "type": "string", "nullable": false}
      ],
      "metrics": []
    }
  ]
}
```

The catalog contains no rows, sample values, bindings, permission tokens, model labels, scope identifiers, tenant details, or scope-provider implementation. A normal authenticated user without the resource permission receives `HTTP 200` with `{"resources": []}` rather than learning that the hidden resource exists.

### 5. Submit the deterministic query

Using the same session-authenticated client:

```python
import json

response = client.post(
    "/asklens/query/",
    data=json.dumps({"question": "List my order statuses"}),
    content_type="application/json",
)
assert response.status_code == 200
payload = response.json()
assert payload["response_type"] == "query"
assert payload["plan"]["resource"] == "orders"
assert payload["plan"]["intent"] == "list"
assert payload["columns"][0]["key"] == "status"
```

Current successful behavior is `HTTP 200` with `response_type: "query"`, the revalidated semantic `plan`, typed `columns`, authorized scoped rows in `data`, `row_count`, deterministic `result_metadata`, and a `run_id`. The response also echoes the question submitted by that authorized caller. It must not expose the Django binding, permission token, model label, scope identity, other users' rows, provider envelope, or credentials. Repeating the synthetic request with unchanged scoped data gives the same canonical projection after excluding `run_id` and `duration_ms`.

### 6. Keep denials opaque and diagnose host setup

With the documented session setup, anonymous `GET /asklens/catalog/` and `POST /asklens/query/` currently return `HTTP 403` at the route gate and create no AskLens audit row. A host that replaces the authentication/permission classes owns any transport-level status or envelope differences and must preserve pre-orchestration denial.

A normal authenticated user without the resource permission sees no resource in the catalog. If that user submits the known question anyway, current query behavior is `HTTP 400` with only the safe member error (plus normal run metadata):

```json
{
  "error": {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable."
  }
}
```

Unknown and unauthorized resources deliberately share `asklens.member.unavailable`; the denial performs zero registered application-data SQL and creates one failed audit row in database audit mode. Do not weaken that opacity, return the required permission, or reveal whether a hidden member exists.

Diagnose trusted host setup instead:

1. Run `python manage.py check` and confirm the one `AppConfig.ready()` registration import runs in every process.
2. Verify the host created the intended permission and assigned it to the current user/group; inspect `user.get_all_permissions()` only in trusted server-side diagnostics.
3. Refresh the authenticated request/user after permission changes, then fetch the permission-scoped catalog again.
4. If the resource is visible but execution fails, test the trusted `scope_provider(request)` with the current user and confirm it returns a lazy queryset for the registered model.

Never broaden the default manager, accept client-supplied identity/scope, or expose permission/startup diagnostics through the opaque query error.

### 7. Verify metadata-only audit outcomes

With `AUDIT_MODE="database"` and `AUDIT_INCLUDE_CONTENT=False`, the documented sequence has these current outcomes:

- anonymous route denial: no AskLens audit row because orchestration did not start;
- authenticated hidden-resource query: one failed audit row, stable error code, zero row count, blank question, and an empty operational plan because the member was unavailable;
- each authorized query: one success audit row with row count and a plan containing only resource and intent.

In metadata-only mode the stored question is blank. Audit rows do not persist result rows, raw rejected input, complete validated plans, filters, private bindings, permission tokens, model labels, scope identifiers, provider payloads, or credentials. The authorized HTTP caller still receives the current query response described above; do not copy that response, its rows, or its echoed question into another audit/log sink by default.

Run detail deliberately changed during alpha. `GET /asklens/runs/<id>/` first applies the configured API permission classes, then permits the row owner or a user with global `asklens.view_semanticqueryrun`; `is_staff` alone no longer grants cross-user review. Inaccessible and missing IDs return the same opaque `404`, and reads create no audit row. Unless the current `AUDIT_INCLUDE_CONTENT` value is exactly boolean `True`, display blanks the question and reduces even a legacy full-content plan to resource/intent metadata. Stored free-form errors are never reflected: recognized codes become canonical safe `{code, message}`, unknown/malformed text becomes a fixed generic safe error, and success/blank errors become `null`.

`AUDIT_DATABASE_ALIAS=None` preserves ordinary Django read/write routing. A trusted non-empty alias is used explicitly for built-in database audit writes and run-detail reads, cannot come from client input, and never falls back to `default`; invalid or unavailable configuration fails with fixed safe read behavior or normal sink-failure handling. Lifecycle commands keep their independent explicit `--database` selection. If full content is enabled, the host owns retention, access, redaction, deletion, backup/replica handling, and every display/export surface.

Route authentication and member/scope validation do not bound request volume or database runtime. Configure host-owned throttling, concurrency limits, statement timeout, and request timeout before production-like use; see [Host throttling and audit controls](host-throttle-and-audit-controls.md). Keep read-only database defense, retention, access, redaction, deletion, monitoring, and any custom sink policy host-owned as well.

Run the matching disposable exact-wheel check from a current source checkout with:

```bash
bash scripts/quickstart-core-smoke.sh --api
```

The smoke prints only provenance hashes, counts, HTTP statuses, the stable denial code, audit booleans/statuses, and cleanup markers—not rows, questions, usernames, permission tokens, scope identifiers, or raw payloads.

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
    timezone="UTC",
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

Every resource must resolve to `global` or `context_scoped`. `DEFAULT_SCOPE_MODE` can only be `context_scoped`; global resources must declare `scope_mode="global"` individually. Context-scoped resources require a trusted `scope_provider`; missing or invalid scope never falls back to the default manager. Every resource must also declare a valid server-owned IANA `timezone`; plans cannot override it and AskLens does not inherit Django's `TIME_ZONE`.

## 2. Configure a provider

AskLens ships with `DummyProvider`, which maps exact questions to deterministic envelopes containing `query_plan` plus optional `presentation`. It is useful for tests, local demos, and evaluation fixtures.

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
                "order_by": [{"metric": "order_count", "direction": "desc"}],
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

## 3. Discover machine features and visible resources

With the optional `api` extra installed, query two separate metadata documents:

```http
GET /asklens/capabilities/
GET /asklens/catalog/
```

Machine capabilities describe supported intents, canonical type/operator rules,
time grains, structural limits, features, aggregate policies, and backend
restrictions. They contain no resources or human prose. The permission-scoped
catalog separately contains visible resources, fields, metrics, enum metadata,
and server-owned resource timezones. Neither response contains rows or sample
values. Abbreviated examples of the two documents follow.

```json
{
  "intents": ["list", "aggregate"],
  "filter_logic": "implicit_and",
  "types": [
    {"name": "enum", "operators": ["eq", "neq", "in", "isnull"]}
  ],
  "time_grains": ["day", "week", "month", "quarter", "year"]
}
```

```json
{
  "resources": [
    {
      "name": "orders",
      "label": "Orders",
      "timezone": "UTC",
      "fields": [
        {"name": "status", "label": "Status", "type": "enum", "nullable": false}
      ],
      "metrics": [
        {"name": "order_count", "label": "Number of orders", "result_type": "integer"}
      ]
    }
  ]
}
```

Users can ask human help questions through `/asklens/query/`. Live mode uses
permission-scoped provider guidance derived from the catalog, but that guidance
is not merged into the machine capability document. Provider-backed suggestions
include catalog references, and AskLens synthesizes/validates executable
QueryPlans locally. Dummy/offline mode uses deterministic help.

## 4. Query through the optional API

For production-like API posture, configure host-side throttling, request timeout,
and concurrency controls before execution and before any transport retry logic.
See [Host throttling and audit controls](host-throttle-and-audit-controls.md).
```http
POST /asklens/query/
Content-Type: application/json

{"question": "Show orders by status"}
```

A successful data-query response includes `response_type: "query"`, the question, validated plan, column metadata, normalized rows, limit metadata, optional presentation, timing, and audit run id. Presentation is outside QueryPlan and cannot affect authorization, scope, compilation, ordering, limits, or returned values. In live mode, deciding between data query and capability help plus producing the data `QueryPlan` and optional presentation happens in one provider call. Advanced clients may submit a previously returned `query_help.suggestions[].plan` with the question; AskLens revalidates the plan against current request permissions and executes it directly instead of making another LLM call.

For local benchmark checks on the synthetic project, use [Synthetic performance
baseline](performance-baseline.md).

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
  "presentation": {
    "kind": "bar",
    "x": {"field": "status", "label": "Status", "type": "enum"},
    "y": {"field": "order_count", "label": "Number Of Orders", "type": "integer"}
  },
  "run_id": 1
}
```

For grouped aggregate/chart responses, `limit` caps returned groups/slices; for list responses it caps returned rows. AskLens fetches `limit + 1` internally and returns at most `limit`, so `result_metadata.truncated` is true only when another matching row/group exists. Ungrouped aggregates have effective limit one and always report `truncated: false`. On an empty scope they still return one row: count metrics are `0` and sum/average/minimum/maximum metrics are `null`; empty grouped aggregates return no rows. This metadata is accurate truncation detection, not cursor pagination.

Column metadata includes canonical `type` and `nullable`. Decimal values are JSON strings, floats are JSON numbers, and unknown runtime objects are rejected rather than stringified. See [Registration](registration.md) for the per-type operator matrix and explicit enum aliases.

Capability/help questions return a non-row response and do not execute a database query. In live mode, `query_help_source` is `semantic_provider` when the unified provider response chose capability help and suggestions passed catalog-reference plus locally synthesized plan validation. An abbreviated response is:

```json
{
  "question": "What can I query?",
  "response_type": "capabilities",
  "routing_source": "fallback",
  "query_help_source": "deterministic",
  "capabilities": {"intents": ["list", "aggregate"], "filter_logic": "implicit_and"},
  "catalog": {"resources": [{"name": "orders", "label": "Orders"}]},
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
- AskLens does not expose a separate `/asklens/help/` endpoint in alpha. Clients should use `/asklens/capabilities/` for machine features, `/asklens/catalog/` for visible resources, and `/asklens/query/` for natural-language help questions.

Submitted plans are always revalidated. This applies to clicked suggestions, browser-saved plans, project-owned saved queries, and custom UI controls that modify filters, dates, ordering, or limits. A submitted plan is a latency/UX optimization, not a trust boundary or permission bypass.

Server-side saved queries are out of scope for the package alpha. Projects may store their own saved-query records, but should submit saved plans back to `/asklens/query/` so AskLens can revalidate them for the current request before execution.

The packaged frontend is a reference/demo UI for teams that want a zero-dependency starting point. It is not intended to be the supported product shell for every application. Production product experiences should generally build a custom UI on the AskLens API.

The admin query page remains available in alpha as a staff/operator utility and demo surface. It uses the same shared query/help orchestration as `/asklens/query/`; data questions create audit records, while help responses do not query the database or create query-run audit rows. It is not a replacement for a product-specific end-user UI.

## 7. Query from Python

Core Python usage does not require DRF. See the [Core Python API](core-python-api.md) guide for core-only setup, separate machine capabilities and permission-scoped catalog metadata, plan validation, execution, result serialization, and the shared query/help orchestration helper.

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
