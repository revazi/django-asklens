# Installation

This documentation describes the reviewed `0.3.0` release source. Its presence
does not by itself establish a Git tag, PyPI publication, or artifact
provenance. Keep each artifact paired with its exact source commit or immutable
release record. The immutable `0.2.0` release is the supported `0.2.x` upgrade
origin; the historical `0.1.0a1` package was a testing artifact and is not a
supported upgrade origin.

## Prior PyPI release and upgrade origin: 0.2.0

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

The published `0.2.0` files have these independently recorded SHA-256 values:

- wheel: `af0881945d5f5f227332aac8bb13df10d4cf5bd3e54a038acd6545db5640d1d8`
- source distribution: `11af90303fd2d23123e4caa98c6e6cb660b7b8f32d6fba0c57a4554c8d39e022`

Maintainers can re-download, authenticate, and exercise both public artifacts
with `scripts/published-package-smoke.sh`; see the
[release process](releasing.md#rechecking-a-published-release-locally). The
probe removes checkout import shadowing and uses separate core, API, and MCP
environments. This does not make PyPI installation an independent security or
production certification.

## Source checkout and exact local artifacts

Use `uv` when developing in this repository:

```bash
uv sync --group dev
uv run pytest
```

A locally built wheel reports `0.3.0`, but its version alone does not prove
provenance. Verify the source commit and artifact digest. The only supported
upgrade origin for this release is `0.2.0`; no upgrade from the `0.1.0a1`
testing artifact is claimed.

### Exact local release-source package evidence

The opt-in package smoke validates an exact committed local `0.3.0` source:

```bash
bash scripts/alpha-candidate-package-smoke.sh
```

The command requires Python 3.12+, `uv`, Git, `tar`, and a clean source tree. It
exports the exact `HEAD` commit into a temporary build tree, builds exactly one
`0.3.0` wheel and one source distribution, runs Twine and package-content
checks, reports their SHA-256 digests, and runs installed-wheel checks outside
the repository root. It verifies that Docker, Playwright, and psycopg did not
leak into runtime requirements or extras and installs the core, API, and MCP
wheel surfaces in separate temporary environments.

The upgrade probe installs actual `django-asklens==0.2.0` from PyPI in a
disposable environment, applies the exact existing AskLens migrations
(`0001_initial` and `0002_add_admin_query_proxy`), and creates one synthetic
`SemanticQueryRun` row. It then upgrades to the local `0.3.0` wheel, runs
`migrate --plan`, `migrate`, `showmigrations`, `check`, and
`makemigrations --check --dry-run`, and verifies the unchanged graph, preserved
row, proxy model, and AskLens table shape. Both prior-release and local-source
imports must resolve inside the disposable environment rather than the checkout.

This is bounded SQLite package evidence for the supported `0.2.0` origin, not
PostgreSQL or production upgrade certification. It does not test or replace the
`0.1.0a1` testing artifact. The script removes its temporary environments and
artifacts and does not upload, tag, publish, or release anything.

## Authenticated API prerequisites for an exact 0.3.0 source artifact

These prerequisites document the optional provisional DRF adapter in an exact,
locally verified `0.3.0` wheel. Users remaining on `0.2.0` must follow the
immutable `v0.2.0` docs until they upgrade to an exact reviewed `0.3.0`
artifact.

```bash
python -m pip install '/verified/path/django_asklens-0.3.0-py3-none-any.whl[api]'
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
    "OBSERVABILITY_SINK": None,  # optional content-free host callback
    "MCP_ALLOW_ROW_RETURN": False,
    "MCP_MAX_RETURNED_ROWS": 100,
}
```

The default permission gate is `django_asklens.access.IsAuthenticated`, a lightweight class compatible with DRF's `has_permission(request, view)` interface. API projects may set `API_PERMISSION_CLASSES` to DRF permission classes or other DRF-compatible classes. Review the [production checklist](production-checklist.md) before enabling AskLens outside local development.

## Compatibility

The [support lifecycle](support-lifecycle.md) defines how a Python, Django,
PostgreSQL, or optional-adapter line enters or leaves the tested list. It keeps
resolver eligibility and exact-artifact CI evidence separate from the
[narrow governed 0.3.x core boundary](compatibility.md). That boundary is not a
1.0 stability claim and does not govern optional adapter or document shapes.

Current development target:

- Python 3.12+
- Django 5.2 LTS, Django 6.0, or Django 6.1
- Pydantic v2
- Optional API extra: Django REST Framework 3.18+
- Optional MCP extra: FastMCP 3.4+

Installation metadata remains `Django>=5.2,<7.0`, but current CI support evidence is deliberately limited to Django 5.2 LTS, 6.0, and 6.1.
