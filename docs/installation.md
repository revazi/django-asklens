# Installation

Install the exact `0.2.0` release for the package surface you need. The
historical `0.1.0a1` package was a testing artifact and is not a supported
upgrade origin.

## Published PyPI release: 0.2.0

Core package:

```bash
python -m pip install 'django-asklens==0.2.0'
```

Optional DRF API and packaged reference frontend:

```bash
python -m pip install 'django-asklens[api]==0.2.0'
```

Optional FastMCP bridge:

```bash
python -m pip install 'django-asklens[mcp]==0.2.0'
```

Use the immutable [documentation tagged `v0.2.0`](https://github.com/revazi/django-asklens/blob/v0.2.0/README.md). Do not combine `0.2.0` instructions with the historical `0.1.0a1` testing artifact.

## Source checkout and exact local artifacts

Use `uv` when developing in this repository:

```bash
uv sync --group dev
uv run pytest
```

A local wheel reports `0.2.0`, but its version alone does not prove provenance.
Verify the source commit and artifact digest. No compatibility or supported
upgrade from the `0.1.0a1` testing artifact is claimed.

### Exact release package evidence

The opt-in package smoke validates an exact local `0.2.0` artifact:

```bash
bash scripts/alpha-candidate-package-smoke.sh
```

The command requires Python 3.12+, `uv`, Git, `tar`, a clean source tree, and no
stale root `build/` or `django_asklens.egg-info/` directory. It exports the exact
`HEAD` commit into a temporary build tree, checks that Docker,
Playwright, and psycopg did not leak
into runtime requirements or extras, and installs the core, API, and MCP wheel
surfaces in separate temporary environments. A disposable SQLite project
verifies migrations and synthetic migration-state preservation. Every temporary
environment and artifact is removed at exit.

The smoke does not install or replace the `0.1.0a1` testing artifact. Its
migration-state exercise is synthetic SQLite evidence, not a supported upgrade
test. The script does not upload, tag, publish, or release anything.

The smoke creates a disposable SQLite Django project in its temporary workdir,
applies migrations (`0001_initial` and `0002_add_admin_query_proxy`), and creates
one synthetic `SemanticQueryRun` row. It runs `migrate --plan`, `migrate`,
`showmigrations`, `check`, and `makemigrations --check --dry-run`, then verifies
the row, proxy model, and AskLens table shape. This is local SQLite evidence,
not a supported upgrade test or PostgreSQL migration evidence.

## Authenticated API prerequisites for exact 0.2.0 artifacts

These prerequisites document the optional DRF adapter in the `0.2.0` package or
an exact locally verified wheel. They do not imply a supported upgrade from
`0.1.0a1`.

```bash
python -m pip install '/verified/path/django_asklens-0.2.0-py3-none-any.whl[api]'
```

The `[api]` extra installs the existing DRF dependency within the bounds in `pyproject.toml`; it does not install FastMCP or make DRF a core dependency. Add the host authentication/session apps, DRF, AskLens, and the project app that owns registration:

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

Mount the current API routes:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

Apply the normal host auth/contenttypes/session migrations, the host model permissions, and AskLens audit migrations, then check startup registration:

```bash
python -m django migrate
python -m django check
```

Use existing host authentication to create and authenticate normal users and assign Django permissions server-side. AskLens does not add an authentication backend or token endpoint. The default API route gate requires an authenticated request; a host may configure stronger existing DRF-compatible permission classes. Row identity and scope still come only from the current server-owned request and the registered `scope_provider(request)`.

For a disposable source-tree verification that performs these steps with synthetic users, session middleware, `testserver` as the only `ALLOWED_HOSTS` entry, deterministic dummy planning, and metadata-only database audit, run:

```bash
bash scripts/quickstart-core-smoke.sh --api
```

The default command without `--api` remains the U2 core-only exact-wheel smoke. Both modes create one `mktemp`-owned root and remove it on success or failure; neither deletes a caller-owned path. Build and dependency installation may use configured package indexes. The smoke is local current-artifact evidence only—not PostgreSQL, release, upgrade, production, external-usability, or security-certification evidence.

Continue with the [authenticated normal-user API quickstart](usage.md#authenticated-normal-user-api-quickstart) for registration, host permission assignment, catalog-first verification, the current query/denial statuses, and audit expectations.

## Django setup

For core-only use, add AskLens to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_asklens",
]
```

For Python-only usage without DRF, see the [Core Python API](core-python-api.md) guide.

For the optional API integration, add DRF and AskLens to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "rest_framework",
    "django_asklens",
]
```

Include the API URLs:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

Optionally mount the packaged reference frontend:

```python
urlpatterns = [
    path("", include("django_asklens.api.urls")),
    path("", include("django_asklens.frontend.urls")),  # /asklens/ui/
]
```

The packaged frontend is optional and calls the AskLens API routes, so it also requires the `api` extra and API URLs. Production projects can build custom UIs directly on the API; see [Building a custom AskLens UI](custom-ui.md).

Run migrations for AskLens-owned audit models, then verify that startup populated the process-local registry:

```bash
python -m django migrate asklens
python manage.py check_asklens --fail-on-empty
```

`check_asklens` prints only aggregate resource, scope-mode, field, and metric counts. It performs no application-data queries and does not invoke scope providers. Django initializes every installed host app before the command runs, so host `AppConfig.ready()` side effects remain the host's responsibility.

## Minimal settings

```python
DJANGO_ASKLENS = {
    # Optional safe default; global resources must still opt in individually.
    "DEFAULT_SCOPE_MODE": "context_scoped",
    "LLM_BACKEND": "dummy",
    "LLM_MODEL": None,
    "LLM_BASE_URL": "https://api.openai.com/v1",
    "LLM_API_KEY": None,
    "LLM_TIMEOUT_SECONDS": 30,
    "LLM_TEMPERATURE": 0,
    "MAX_ROWS": 500,
    "DEFAULT_LIMIT": 100,
    "MAX_PLAN_BYTES": 65_536,
    "MAX_FILTERS": 20,
    "MAX_SELECTED_FIELDS": 25,
    "MAX_ORDER_BY": 5,
    "MAX_JOINS": 2,  # maximum relationship-hop depth
    "MAX_RELATIONSHIP_EDGES": 8,
    "MAX_IN_VALUES": 100,
    "MAX_FILTER_VALUES": 200,
    "MAX_METRICS": 5,
    "MAX_GROUP_BY": 3,
    "PROMPT_RESOURCE_SHORTLIST_LIMIT": 0,
    "MCP_ALLOW_ROW_RETURN": False,
    "MCP_MAX_RETURNED_ROWS": 100,
}
```

The default permission gate is `django_asklens.access.IsAuthenticated`, a lightweight class compatible with DRF's `has_permission(request, view)` interface. API projects may set `API_PERMISSION_CLASSES` to DRF permission classes or other DRF-compatible classes. Review the [production checklist](production-checklist.md) before enabling AskLens outside local development.

## Compatibility

The [support lifecycle](support-lifecycle.md) defines how a Python, Django,
PostgreSQL, or optional-adapter line enters or leaves the tested list. It keeps
resolver eligibility, exact-artifact CI evidence, and future stable guarantees
separate; no stable compatibility surface has been accepted yet.

Current development target:

- Python 3.12+
- Django 5.2 LTS, Django 6.0, or Django 6.1
- Pydantic v2
- Optional API extra: Django REST Framework 3.18+
- Optional MCP extra: FastMCP 3.4+

Installation metadata remains `Django>=5.2,<7.0`, but current CI support evidence is deliberately limited to Django 5.2 LTS, 6.0, and 6.1.
