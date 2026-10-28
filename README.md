# Django AskLens

[![Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/revazi/django-asklens)
[![PyPI version](https://img.shields.io/pypi/v/django-asklens.svg)](https://pypi.org/project/django-asklens/)
[![PyPI downloads](https://img.shields.io/pypi/dm/django-asklens.svg)](https://pypi.org/project/django-asklens/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-asklens.svg)](https://pypi.org/project/django-asklens/)
[![Django](https://img.shields.io/badge/django-5.2%20%7C%206.0%20%7C%206.1-092E20.svg?logo=django)](https://www.djangoproject.com/)
[![Tests](https://github.com/revazi/django-asklens/actions/workflows/ci.yml/badge.svg)](https://github.com/revazi/django-asklens/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://docs.pydantic.dev)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](https://github.com/revazi/django-asklens/blob/main/LICENSE)
[![Documentation](https://img.shields.io/badge/docs-live-blue.svg)](https://revazi.github.io/django-asklens/)
[![Django Packages](https://img.shields.io/badge/Django%20Packages-django--asklens-8c3c26.svg)](https://djangopackages.org/packages/p/django-asklens/)

Safe natural-language querying over explicitly registered Django models. AskLens does **not** let an LLM write SQL. It asks a provider for structured JSON, validates that plan against your catalog and the current request's permissions, compiles a read-only Django ORM query, and returns table-ready JSON.

`django-asklens==0.3.2` is the current published alpha, not a stable or production-certified release. Its public availability and immutable artifact identity are established by the [`v0.3.2` GitHub Release](https://github.com/revazi/django-asklens/releases/tag/v0.3.2) and [PyPI version record](https://pypi.org/project/django-asklens/0.3.2/). Adapters may still change. Authenticate public artifacts before use; hashes and upgrade origins are in [Installation](docs/installation.md), and the [0.3.2 preparation record](docs/release-preparation-0.3.2.md) preserves the pre-publication candidate scope and evidence.

Django AskLens was created by [Revaz Zakalashvili](https://github.com/revazi).

---

## Try AskLens locally — no API key

Prerequisites are Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and
a source checkout; Docker and provider credentials are not needed. If you do
not already have the repository locally:

```bash
git clone https://github.com/revazi/django-asklens.git
cd django-asklens
uv sync --locked --group dev
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
  uv run python -m django migrate --run-syncdb
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
  uv run python -m django seed_complex_test_project --size small
DJANGO_ASKLENS_DEMO_LIVE_LLM=0 \
  DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
  uv run python -m django runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/>, sign in as `facility-owner` with password
`12admin34`, and click the exact starter question **Show paid billing revenue by
product**. The result should contain North-scoped products such as `North
membership`, never South rows. No provider credentials or network provider call
are involved. Offline mode matches only the displayed exact questions; it does
not support arbitrary natural-language wording. **Show paid billing revenue for
the no-sales demo product** is the intentional successful empty-result example.

This is `0.3.2` release-source demo evidence when viewed at the immutable
`v0.3.2` tag; mutable `main` may be newer. It is not production certification
or external usability evidence. See the [complete start, expected-result,
troubleshooting, security,
host-transition, and cleanup guide](docs/test-project-demo.md#sqlite-frontend-and-admin-first-run-start-to-reset).

### Synthetic browser showcase

[![The AskLens source demo showing the exact “Show paid billing revenue by product” question, North Studio current-user scope, and a grouped North membership result.](https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/scoped-revenue.png)](docs/showcase.md)

*`facility-owner` runs the exact configured question **Show paid billing revenue
by product** against seeded synthetic data. The host-selected scope is North
Studio; the offline deterministic planner makes no network call and does not
support arbitrary wording.*

<a href="docs/showcase.md#opaque-denial"><img src="https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/neutral-denial.png" width="560" alt="The AskLens synthetic demo showing a neutral Access unavailable page with a sign-out action and no permission, resource, or tenant details."></a>

*The smaller denial capture shows the seeded `no-report` account receiving an
opaque host response; it does not disclose the policy or another tenant's
existence.*

[Watch the 36-second browser recording (WebM)](https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/offline-demo.webm)
— Django login, current-user scope, the grouped result above, and the exact
successful empty fixture **Show paid billing revenue for the no-sales demo
product**. The [showcase page](docs/showcase.md) also includes captions, a
text walkthrough, the neutral denial capture, and reproducible no-Docker
capture instructions. All shown credentials and rows are synthetic and
local-only; authentication, CSRF,
explicit catalog, current-request permissions, row scope, and query limits
remain active.

---

## Features

- **No generated SQL** — the model proposes a `QueryPlan`; AskLens validates it and compiles Django ORM only
- **Explicit catalog** — only registered resources, fields, and metrics are queryable
- **Current-request authorization** — resource and field permissions apply to the user making the request
- **Row scope** — context-scoped resources require a trusted `scope_provider(request)` and do not fall back to the model manager
- **Read-only execution** — list and aggregate questions only; AskLens does not create, update, or delete application data
- **Deterministic dummy provider** — exact questions map to reviewed plans, with no network call
- **OpenAI-compatible providers** — optional live planning through an OpenAI-compatible endpoint
- **Optional DRF API** — catalog, capabilities, query, and run-detail endpoints
- **Optional MCP adapter** — the same execution path for MCP clients
- **Audit records** — metadata-only by default; questions and plans stay out unless you opt in
- **UI-agnostic results** — `columns` + `data` JSON for your own table or chart

---

## Installation

After authenticating the public `0.3.2` release artifacts:

```bash
python -m pip install 'django-asklens==0.3.2'
python -m pip install 'django-asklens[api]==0.3.2'   # optional DRF API and reference UI
python -m pip install 'django-asklens[mcp]==0.3.2'   # optional MCP adapter
```

Core dependencies are Django and Pydantic. DRF and the MCP stack are extras, not required to register resources or call `execute_plan()`.

This is an alpha package. Confirm the wheel or sdist digest in [Installation](docs/installation.md) before installing. A same-version local rebuild is not the public artifact.

---

## Quick start

### 1. Add the app

```python
INSTALLED_APPS = [
    # ...
    "rest_framework",
    "django_asklens",
]
```

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

```bash
python -m django migrate asklens
```

For a path with no DRF, provider call, or frontend, use the [Core-only executable quickstart](docs/quickstart-core.md).

### 2. Register one resource

Import this once from your app's `AppConfig.ready()`. Bindings stay private; plans use the semantic names.

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

### 3. Start with the dummy provider

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
            "presentation": {"kind": "bar", "x": "status", "y": "order_count"},
        }
    },
}
```

### 4. Ask

AskLens uses the host's existing authentication. It does not provide a login or token endpoint. The optional API quickstart uses a host-created authenticated user and checks that user's permission-scoped catalog first. See the [Authenticated normal-user API quickstart](docs/usage.md#authenticated-normal-user-api-quickstart).

```http
POST /asklens/query/
Content-Type: application/json

{"question": "Show orders by status"}
```

```json
{
  "run_id": 1,
  "question": "Show orders by status",
  "response_type": "query",
  "result": {
    "columns": [
      {"key": "status", "label": "Status", "type": "string", "nullable": false},
      {"key": "order_count", "label": "Orders", "type": "integer", "nullable": false}
    ],
    "data": [{"status": "paid", "order_count": 12}],
    "row_count": 1,
    "duration_ms": 4,
    "result_metadata": {"limit": 100, "limit_scope": "groups", "truncated": false}
  },
  "presentation": {"kind": "bar"}
}
```

Help questions such as `show me example queries` return capabilities and a permission-scoped catalog. They do not run a database query.

---

## Optional UI and live providers

Render `result.columns` and `result.data` in your own UI. The packaged page is a demo, not a product frontend:

```python
urlpatterns = [
    path("", include("django_asklens.api.urls")),
    path("", include("django_asklens.frontend.urls")),  # /asklens/ui/
]
```

The default backend makes no network calls. An OpenAI-compatible provider is opt-in:

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

See [Provider configuration](docs/providers.md) and [Building a custom AskLens UI](docs/custom-ui.md).

---

## Security

- Unregistered models, fields, and metrics are not queryable.
- `global` scope must be explicit. Context-scoped resources fail closed without a trusted scope provider.
- Sensitive fields stay hidden unless the current user has the field permission.
- Plans are size-limited before compilation. AskLens executes read-only ORM queries only.
- The query API rejects unknown body keys, including client policy claims, before execution.
- Default audit records omit the question, filter values, and complete plan.
- AskLens does not send database rows, sample values, or secrets to providers by default.

Review the [security checklist](docs/security-checklist.md) and [production checklist](docs/production-checklist.md) before using AskLens outside local development. This alpha is not a production-security certification. Host applications still own authentication, scope policy, timeouts, and rate limits.

---

## Requirements

| Dependency | Version |
| --- | --- |
| Python | >= 3.12 |
| Django | >= 5.2, < 7.0 |
| Pydantic | >= 2, < 3 |

Installation metadata remains `Django>=5.2,<7.0`, but current CI support evidence is deliberately limited to Django 5.2 LTS, 6.0, and 6.1.

Release checks cover Python 3.12 and 3.13.

---

## Documentation

- [Live documentation and showcase](https://revazi.github.io/django-asklens/)
- [Installation](docs/installation.md)
- [Core-only executable quickstart](docs/quickstart-core.md)
- [Authenticated normal-user API quickstart](docs/usage.md#authenticated-normal-user-api-quickstart)
- [Usage guide](docs/usage.md)
- [Registration API](docs/registration.md)
- [Provider configuration](docs/providers.md)
- [MCP integration](docs/mcp-integration.md)
- [Security checklist](docs/security-checklist.md)
- [source demo frontend/admin first run](docs/test-project-demo.md#sqlite-frontend-and-admin-first-run-start-to-reset)
- [Synthetic browser showcase and reproducible capture](docs/showcase.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

---

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The opt-in synthetic browser smoke is `bash scripts/reference-demo-smoke.sh` after `uv run playwright install chromium`. It is contributor evidence, not production certification.

---

## License

BSD 3-Clause. See [LICENSE](LICENSE).
