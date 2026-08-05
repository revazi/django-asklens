# Installation

Django AskLens is currently alpha. Install the core package into a Django project from your chosen source:

```bash
python -m pip install django-asklens
```

Install the optional DRF API integration when you want the built-in HTTP endpoints or packaged reference frontend:

```bash
python -m pip install 'django-asklens[api]'
```

Install the optional MCP integration when you want the FastMCP bridge helpers for exposing AskLens through a real MCP transport:

```bash
python -m pip install 'django-asklens[mcp]'
```

For local development in this repository, use `uv`:

```bash
uv sync --group dev
uv run pytest
```

## Source-checkout alpha-candidate package evidence

R4 includes an opt-in package smoke for proposal evidence only:

```bash
bash scripts/alpha-candidate-package-smoke.sh
```

The command requires Python 3.12+, `uv`, and network access to PyPI. It builds the current source into a temporary wheel, checks that Docker, Playwright, and psycopg did not leak into runtime requirements or extras, and installs the core, API, and MCP wheel surfaces in separate temporary environments. It then installs the published 0.1.0a1 from PyPI and replaces it with the exact local source wheel before rerunning the installed-core smoke. Every temporary environment and artifact is removed at exit.

The repository version intentionally remains `0.1.0a1` because no version bump or release is authorized. Consequently, the final step must use pip's same-version `--force-reinstall`; it is package replacement evidence, not proof of a normal resolver-selected `0.1.0a1` to `0.2.0a*` transition. A separately authorized candidate must set the exact proposed version and rerun this workflow as a normal upgrade. The script does not upload, tag, publish, or release anything.

For PR10 evidence, the script now creates a disposable SQLite Django project in its temporary workdir, applies the published package migrations (`0001_initial` and `0002_add_admin_query_proxy`), and then creates one synthetic `SemanticQueryRun` row. It then replaces the install with the exact local wheel, re-runs `migrate --plan`, `migrate`, `showmigrations`, `check`, and `makemigrations --check --dry-run`, and verifies that the synthetic row, proxy model, and AskLens table shape survive. This is migration-state preservation evidence only, not a normal package upgrade claim, not PostgreSQL migration evidence, and not release evidence.

## Private candidate evaluation

Maintainer-invited evaluators using an immutable commit, source-built wheel, and checksum should follow the [private candidate evaluation and onboarding guide](private-candidate-evaluation.md). That workflow uses a clean participant-owned staging environment and verified local artifact rather than assuming a public candidate exists on PyPI. It keeps completed forms and evidence outside the repository and does not turn the unchanged `0.1.0a1` package replacement into an upgrade or beta claim. An optional [Privacy-Safe Pilot Intake Worksheet](pilot-intake-worksheet.md) template is provided for structing private evaluations safely.

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
- Django 5.2 LTS or Django 6.x
- Pydantic v2
- Optional API extra: Django REST Framework 3.17+
- Optional MCP extra: FastMCP 3.4+

Current package metadata and CI target Django 5.2 LTS and Django 6.x.
