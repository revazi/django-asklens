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
    "LLM_BACKEND": "dummy",
    "LLM_MODEL": None,
    "LLM_BASE_URL": "https://api.openai.com/v1",
    "LLM_API_KEY": None,
    "LLM_TIMEOUT_SECONDS": 30,
    "LLM_TEMPERATURE": 0,
    "MAX_ROWS": 500,
    "MAX_JOINS": 2,
    "MAX_METRICS": 5,
    "MAX_GROUP_BY": 3,
    "PROMPT_RESOURCE_SHORTLIST_LIMIT": 0,
    "ALLOW_RAW_SQL": False,
    "SEND_SAMPLE_ROWS_TO_LLM": False,
    "DEFAULT_VISUALIZATION": "table",
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
