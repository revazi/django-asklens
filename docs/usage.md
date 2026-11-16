# Usage guide

For setup failures or safe query recovery, follow the
[troubleshooting decision path](troubleshooting.md). Registry counts, migration
readiness, request authorization and successful empty results are separate states.
For a small host-model declaration, start with the
[one-field scoped registration](registration.md#start-with-one-scoped-field)
and [equivalent before/after example](registration.md#beforeafter-less-presentation-boilerplate-same-policy).
No model discovery or new registration helper is needed.

## Authenticated normal-user API quickstart

After [Your first scoped question](quickstart-app.md), choose **one** adapter.
Reuse that copied application's model, migration, exact dummy questions,
`shop.apps.ShopConfig`, and single `AppConfig.ready()` registration import;
do not copy the complex test project. These recipes use existing immutable public
`django-asklens==0.3.2` capabilities, but the new `examples/quickstart` adapter
files are **source-only additions**, absent from immutable public artifacts.
Authenticate the public wheel via [Installation](installation.md); a same-version
candidate rebuild is separate evidence. The historical `0.1.0a1` artifact is not
a supported upgrade origin.

HTTP, admin/frontend, MCP, settings, and question orchestration are
[provisional](compatibility.md), not frozen 0.3.x wire contracts. All defaults
below are synthetic, offline, metadata-only audited, and local-only, not a
production authentication/deployment template.

### 1. Choose dependencies and settings

From the copied quickstart directory with its authenticated wheel in `artifacts/`:

| Path | Install in the existing `.venv` | Settings module | Needs DRF? |
| --- | --- | --- | --- |
| API + custom table or packaged browser UI | `uv pip install --python .venv/bin/python 'artifacts/django_asklens-0.3.2-py3-none-any.whl[api]'` | `quickstart.api_settings` | Yes: the `api` extra |
| Native Django admin query + view-only audit admin | Existing core wheel is sufficient | `quickstart.web_settings` | **No** |
| MCP helpers / FastMCP bridge | See [MCP recipe](mcp-integration.md#bounded-mcp-quickstart) | `quickstart.mcp_settings` | No |

No separate admin extra exists. The core requires `Django>=5.2,<7.0` and
`pydantic>=2,<3`; `api` adds `djangorestframework>=3.18,<4.0` only. Installing an
extra into an existing environment does not remove other extras: start fresh
when checking dependency isolation.

The opt-in [web settings](https://github.com/revazi/django-asklens/blob/main/examples/quickstart/quickstart/web_settings.py)
add Django sessions, messages, admin, staticfiles, DjangoTemplates with request,
auth and messages context processors, and this middleware stack:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
```

`quickstart.api_settings` additionally adds `"rest_framework"` to
`INSTALLED_APPS` and explicitly sets DRF's `DEFAULT_AUTHENTICATION_CLASSES` to
`["rest_framework.authentication.SessionAuthentication"]`. Both keep the core
`DJANGO_ASKLENS` dummy/audit settings and explicitly set:

```python
# After importing core settings; preserve the configured DUMMY_PLANS.
DJANGO_ASKLENS = {
    **DJANGO_ASKLENS,
    "API_PERMISSION_CLASSES": ["django_asklens.access.IsAuthenticated"],
    "REQUEST_PERMISSIONS_GETTER": None,
}
```

The route gate authenticates the caller; the default permission getter calls
`request.user.get_all_permissions()` for the **current request**. It does not
accept client claims. If replacing `REQUEST_PERMISSIONS_GETTER`, derive only
server-owned permissions from that authenticated request. The existing resource's
`requires_permission="shop.view_order"` and `visible_orders(request)` then
independently enforce member visibility and `Order.objects.filter(owner_id=user.pk)`.
Anonymous scope returns `Order.objects.none()`; missing/invalid scope never
falls back to an unrestricted manager. Permission tokens, bindings, protected
fields, and scope identities must not appear in API, catalog, or audit responses.

### 2. Wire routes and host authentication

The committed URL modules are deliberately small:

```python
# quickstart/web_urls.py: Django-only admin
from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
```

```python
# quickstart/api_urls.py: API plus host-owned login/table views (see source)
from django.urls import include, path
from .web_urls import urlpatterns as admin_urls

urlpatterns = [*admin_urls, path("", include("django_asklens.api.urls"))]
```

The actual `api_urls.py` also mounts Django's `LoginView` at `/accounts/login/`
and a `login_required` template view at `/table/`. These are **host example
code**, not AskLens authentication endpoints. The packaged browser UI is a
separate optional shell; see [Optional packaged frontend](#5-optional-packaged-frontend).
It and this custom table call the API and require the API extra. The native
admin query form POSTs directly to Django and does not.

Migrate/check the chosen stack (use `web_settings` instead for admin only):

```bash
.venv/bin/python manage.py migrate --settings=quickstart.api_settings
.venv/bin/python manage.py check --settings=quickstart.api_settings
.venv/bin/python manage.py check_asklens --fail-on-empty --settings=quickstart.api_settings
```

Keep real host authentication, HTTPS, secure cookies, CSRF, and session policy
host-owned. Do not publish `--as-user`, username/tenant selection, or an identity
header as authentication. The base seed's three normal users have unusable
passwords and cannot log in. Executable recipe tests set a **test-only** password
inside disposable test databases and submit the real Django login form with
CSRF; no login credentials are seeded, printed, or required from the reader.
Admin tests create a separate synthetic staff user with the resource permission
and owned fixtures; `is_staff` alone does not authorize rows. Do not make users
superusers or weaken seeding safeguards to get a query working.

### 3. Verify table-ready success, empty, and opaque denial

The following marked commands are replayed from this guide by the installed
candidate-wheel harness. They create and destroy their own test database; the
existing quickstart database and unusable-password seed stay unchanged.

<!-- asklens-adapter:api -->
```bash
.venv/bin/python manage.py test shop.api_recipe --settings=quickstart.api_settings
```

<!-- asklens-adapter:core -->
```bash
.venv/bin/python manage.py test shop.admin_recipe --settings=quickstart.web_settings
```

| Current-request outcome | Session API | Native admin query page |
| --- | --- | --- |
| Anonymous | Catalog/query `HTTP 403`; no orchestration/audit | Redirect to `/admin/login/` |
| Authenticated POST without CSRF | `HTTP 403`, safe authorization error, no audit | `HTTP 403`, no audit |
| Exact `Show my paid orders`, authorized owner | `HTTP 200`, `response_type: "query"`, complete `result` | `HTTP 200`, Product/Total table with the same scoped cells |
| Exact `Show my refunded orders`, authorized owner | `HTTP 200`, typed columns, `data: []`, `row_count: 0` | `HTTP 200`, “No rows” — successful empty state |
| Same paid question after resource permission removal | Catalog becomes `{"resources": []}`; query `HTTP 400`, `asklens.member.unavailable` | `HTTP 200` form with “A requested query member is unavailable.” and no result table |

Successful API `result.columns` keys are `product` and `total_cents`.
`result.data` is exactly the Alice data in the [minimal quickstart](quickstart-app.md#4-ask-an-exact-question),
never Bob's row or the draft order. `result.result_metadata.truncated` is false.
The API echoes the authorized caller's question and semantic plan; do not log
those response bodies. The admin renders the same columns/data as cells, not a
second execution path. See the [minimal safe columns/data consumer](custom-ui.md).

The tests revoke the permission **between requests** and execute a previously
known question again. Denial performs zero registered application-data SQL.
Unknown and unauthorized members have the same opaque error; do not infer
protected fields, permissions, or tenant existence. Admin route-gate denial
instead returns `HTTP 403` before orchestration. Do not display raw errors,
permission diagnostics, provider bodies, or audit records as recovery hints.

### 4. Audit and safe recovery

With `AUDIT_MODE="database"` and `AUDIT_INCLUDE_CONTENT=False`, each accepted
success/empty attempt creates one success audit row; an accepted member denial
creates one failed audit row. The stored question is blank and the operational
plan contains only resource and intent. Anonymous/CSRF/route-gate denials create
no audit row. Keep metadata-only defaults and host-owned retention/access;
never enable full content for onboarding convenience.

The `SemanticQueryRun` admin remains **view-only**, including for superusers:
no add/change/delete or bulk delete. Give trusted reviewers only the intended
Django audit-view permission, not ordinary query users cross-user audit access.
The recipe verifies this with direct mutation POSTs as well as missing UI
controls. Query permission is not audit permission. For provisional run-detail
visibility/redaction and audit routing, see [Query through the optional API](#4-query-through-the-optional-api).

If setup fails, run migrations and system checks, verify the one registration
import, and inspect permission assignment and the trusted scope provider only
in server-side diagnostics. Refresh the user/request after permission changes;
never return permission lists or broaden the queryset to recover. Dummy mode
answers **only** the exact configured questions. Host-owned throttling,
concurrency limits, statement timeout, and request timeout are still necessary;
see [Host controls](host-throttle-and-audit-controls.md).

For installed evidence, build a local candidate and reuse the existing installer:

```bash
uv run --no-sync python -m build --wheel
ASKLENS_ADAPTER_SMOKE=1 uv run --no-sync bash .github/scripts/wheel-smoke.sh core 'Django>=5.2,<5.3' '5.2.'
ASKLENS_ADAPTER_SMOKE=1 uv run --no-sync bash .github/scripts/wheel-smoke.sh api 'Django>=5.2,<5.3' '5.2.'
```

It copies the actual consumer outside the checkout, checks installed wheel bytes
and optional-dependency isolation before/after execution, blocks execution-time
network calls, and replays the marked commands above. Core/admin is checked
**without DRF**; API is checked without FastMCP. Candidate smoke evidence is not
public-PyPI artifact authentication, production wire acceptance, independent
adoption, or security certification. Environment installation may use network
access; recipe execution does not. The [custom UI verification](custom-ui.md#verification-and-evidence-limits)
adds an optional installed-server Chromium replay using the same installer;
its only HTTP is to the owned local synthetic test server.

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

A successful data-query response includes `response_type: "query"`, the question,
validated plan, a complete `result` child, optional presentation, and audit run
id. The result child contains column metadata, normalized rows, row count,
timing, deterministic limit metadata, and optional `empty: true`. Presentation
is outside QueryPlan and cannot affect authorization, scope, compilation,
ordering, limits, or returned values. In live mode, deciding between data query
and capability help plus producing the data `QueryPlan` and optional
presentation happens in one provider call. Advanced clients may submit a
previously returned `help.content.suggestions[].plan` with the question; AskLens
revalidates the plan against current request permissions and executes it
directly instead of making another LLM call.

For local benchmark checks on the synthetic project, use [Synthetic performance
baseline](performance-baseline.md).

```json
{
  "question": "Show orders by status",
  "response_type": "query",
  "plan": {"resource": "orders", "intent": "aggregate", "limit": 10},
  "result": {
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
    "row_count": 1,
    "duration_ms": 4,
    "result_metadata": {
      "limit": 10,
      "limit_scope": "groups",
      "truncated": false
    }
  },
  "presentation": {
    "kind": "bar",
    "x": {"field": "status", "label": "Status", "type": "enum"},
    "y": {"field": "order_count", "label": "Number Of Orders", "type": "integer"}
  },
  "run_id": 1
}
```

For grouped aggregate/chart responses, `result.result_metadata.limit` caps
returned groups/slices; for list responses it caps returned rows. AskLens fetches
`limit + 1` internally and returns at most `limit`, so
`result.result_metadata.truncated` is true only when another matching row/group
exists. Ungrouped aggregates have effective limit one and always report
`truncated: false`. On an empty scope they still return one row: count metrics
are `0` and sum/average/minimum/maximum metrics are `null`; empty grouped
aggregates return no rows and add `result.empty: true`. This metadata is accurate
truncation detection, not cursor pagination.

Column metadata includes canonical `type` and `nullable`. Decimal values are JSON strings, floats are JSON numbers, and unknown runtime objects are rejected rather than stringified. See [Registration](registration.md) for the per-type operator matrix and explicit enum aliases.

Capability/help questions return a non-row response and do not execute a
database query. In live mode, `help.source` is `semantic_provider` when the
unified provider response chose capability help and suggestions passed catalog-
reference plus locally synthesized plan validation. The exact machine documents
remain separate from adapter routing and human help:

```json
{
  "question": "What can I query?",
  "response_type": "capabilities",
  "routing": {"intent": {"intent": "capabilities"}, "source": "fallback"},
  "capabilities": {"intents": ["list", "aggregate"], "filter_logic": "implicit_and"},
  "catalog": {"resources": [{"name": "orders", "label": "Orders"}]},
  "help": {
    "source": "deterministic",
    "content": {
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
}
```

`help.content` is not an internal machine document. A safe provider fallback
reason, when present, is `help.error`.

### HTTP failures and audit visibility

Every handled failure from the four AskLens DRF views has one route-local shape:

```json
{
  "error": {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable."
  }
}
```

Only an accepted database-audited failure may add top-level `run_id`. Failure
bodies never add `response_type`, echo `question`, repeat `status`, or expose
DRF `detail`. Parser/media/method failures use `asklens.parse.invalid`;
authentication/permission/debug denials use `asklens.authorization.denied`;
missing/inaccessible runs and unknown/unauthorized query members use
`asklens.member.unavailable`; throttling uses `asklens.budget.exceeded`; and
audit-unavailable/unexpected failures use `asklens.execute.failed`. Applicable
`Allow`, `WWW-Authenticate`, and `Retry-After` headers are preserved. Replacing
host authentication classes may change statuses/headers, but must preserve
pre-orchestration denial and the safe AskLens error envelope.

`POST /asklens/query/` accepts only `question`, `debug`, `include_presentation`,
`plan`, and `presentation` at the top level. Unknown keys (including user,
permission, tenant, scope, or audit-routing claims) fail before orchestration,
audit, or application-data SQL, without reflecting rejected input/diagnostics.
Catalog metadata contains no rows, sample values, bindings, permission tokens,
model labels, scope identifiers, or tenant details.

Metadata-only audit stores no result rows, complete plans, filters, private
bindings, permission tokens, model labels, scope identifiers, provider payloads,
or credentials. Do not copy authorized HTTP response bodies into another log
or audit sink by default.

`GET /asklens/runs/<id>/` first applies API route gates, then requires row
ownership or global `asklens.view_semanticqueryrun`; `is_staff` alone does not
grant cross-user review. Missing/inaccessible IDs share an opaque `404`; reads
create no audit row. Unless current `AUDIT_INCLUDE_CONTENT` is exactly boolean
`True`, display blanks the question and reduces even legacy full-content plans
to resource/intent. Stored free-form errors are never reflected: recognized
codes become canonical safe errors; unknown/malformed text becomes a fixed
safe generic error; success/blank errors become `null`.

`AUDIT_DATABASE_ALIAS=None` preserves Django routing. A trusted non-empty alias
explicitly controls built-in database audit writes and run-detail reads, never
comes from client input, and never falls back to `default`. Invalid/unavailable
configuration fails with safe read/sink-failure behavior. Lifecycle commands
retain their independent explicit `--database` selection. If full content is
enabled, the host owns retention, access, redaction, deletion, backups/replicas,
and every display/export surface; it is not required for any recipe here.

## 5. Optional packaged frontend

Projects that want full control over layout, tables, charts, or saved-query UX can build a custom UI directly on the AskLens API; see [Building a custom AskLens UI](custom-ui.md).

Projects that want a built-in reference/demo UI must install the `api` extra
and mount the AskLens frontend (no separate browser framework/build toolchain).
It calls the same API endpoints and uses host Django session authentication. Users can save useful questions locally in their browser; saved plans are sent back only as normal query requests and are revalidated against current permissions before execution.

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
