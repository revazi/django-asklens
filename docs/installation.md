# Installation

Choose instructions by artifact provenance. The published PyPI alpha, the unreleased `main` source tree, and a maintainer-supplied private candidate are different contexts and are not interchangeable.

## Published PyPI alpha: 0.1.0a1

PyPI currently serves only the published `django-asklens==0.1.0a1` alpha. Use an exact version pin for the surface you need.

Core package:

```bash
python -m pip install 'django-asklens==0.1.0a1'
```

Optional DRF API and packaged reference frontend:

```bash
python -m pip install 'django-asklens[api]==0.1.0a1'
```

Optional FastMCP bridge:

```bash
python -m pip install 'django-asklens[mcp]==0.1.0a1'
```

Use the immutable [published-alpha documentation tagged `v0.1.0a1`](https://github.com/revazi/django-asklens/blob/v0.1.0a1/README.md). Do not use the current `main` README quickstart with this package: `main` documents an incompatible, unreleased 0.2 target.

## Unreleased main/source checkout for contributors

The current `main` branch is contributor source for an incompatible 0.2 target. It is not a release or release candidate, not a PyPI upgrade, and not a public package installation path. No public 0.2 package is created by these instructions.

Use `uv` when developing in this repository:

```bash
uv sync --group dev
uv run pytest
```

Do not mix the published-alpha artifact with source-built main artifacts across workers, clients, or environments. A wheel built from current source still reports `0.1.0a1`; replacing the published wheel with those different same-version bytes requires an exact local artifact and `--force-reinstall`. Call that same-version replacement evidence. It is not a normal upgrade or release.

### Source-checkout alpha-candidate package evidence

R4 includes an opt-in package smoke for proposal evidence only:

```bash
bash scripts/alpha-candidate-package-smoke.sh
```

The command requires Python 3.12+, `uv`, and network access to PyPI. It builds the current source into a temporary wheel, checks that Docker, Playwright, and psycopg did not leak into runtime requirements or extras, and installs the core, API, and MCP wheel surfaces in separate temporary environments. It then installs the published 0.1.0a1 from PyPI and replaces it with the exact local source wheel before rerunning the installed-core smoke. Every temporary environment and artifact is removed at exit.

The repository version intentionally remains `0.1.0a1` because no version bump or release is authorized. Consequently, the final step uses pip's same-version `--force-reinstall` only as package replacement evidence; it does not prove a resolver-selected version transition. A future separately authorized candidate would need its own exact version and evidence. The script does not upload, tag, publish, or release anything.

For PR10 evidence, the script creates a disposable SQLite Django project in its temporary workdir, applies the published package migrations (`0001_initial` and `0002_add_admin_query_proxy`), and creates one synthetic `SemanticQueryRun` row. It then replaces the install with the exact local wheel, re-runs `migrate --plan`, `migrate`, `showmigrations`, `check`, and `makemigrations --check --dry-run`, and verifies that the synthetic row, proxy model, and AskLens table shape survive. This is same-version replacement and migration-state preservation evidence only, not PostgreSQL migration evidence and not release evidence.

## Maintainer-supplied private candidate evaluation

This context applies only when a maintainer supplies an exact local wheel through an approved channel. Before any installation, require all three manifest values:

- an immutable 40-character Git commit;
- the exact wheel filename;
- the wheel's SHA-256 digest.

Do not rely on the shared `0.1.0a1` version or filename: verify all three before installing. Only after that verification, follow the [private candidate evaluation and onboarding guide](private-candidate-evaluation.md), which performs commit and SHA-256 checks before its local-wheel installation step.

A current private candidate still reports `0.1.0a1`, so installing it is exact same-version replacement in an isolated environment, not a normal PyPI upgrade or public release. The guide does not authorize a version, tag, upload, beta, or production use. It keeps completed forms and evidence outside the repository. An optional [Privacy-Safe Pilot Intake Worksheet](pilot-intake-worksheet.md) template helps structure private evaluations safely.

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

Run migrations for AskLens-owned audit models:

```bash
python -m django migrate asklens
```

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
    "ALLOW_RAW_SQL": False,
    "SEND_SAMPLE_ROWS_TO_LLM": False,
    "MCP_ALLOW_ROW_RETURN": False,
    "MCP_MAX_RETURNED_ROWS": 100,
}
```

The default permission gate is `django_asklens.access.IsAuthenticated`, a lightweight class compatible with DRF's `has_permission(request, view)` interface. API projects may set `API_PERMISSION_CLASSES` to DRF permission classes or other DRF-compatible classes. Review the [production checklist](production-checklist.md) before enabling AskLens outside local development.

## Compatibility

Current development target:

- Python 3.12+
- Django 5.2 LTS, Django 6.0, or Django 6.1
- Pydantic v2
- Optional API extra: Django REST Framework 3.18+
- Optional MCP extra: FastMCP 3.4+

Installation metadata remains `Django>=5.2,<7.0`, but current CI support evidence is deliberately limited to Django 5.2 LTS, 6.0, and 6.1.
