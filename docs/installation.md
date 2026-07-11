# Installation

Django AskLens is currently alpha. Install it into a Django project from your chosen source.

```bash
python -m pip install django-asklens
```

For local development in this repository, use `uv`:

```bash
uv sync --group dev
uv run pytest
```

## Django setup

Add AskLens and DRF to `INSTALLED_APPS`:

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

The packaged frontend is optional. Production projects can build custom UIs directly on the API; see [Building a custom AskLens UI](custom-ui.md).

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
}
```

The default API permission class is `rest_framework.permissions.IsAuthenticated`. Review the [production checklist](production-checklist.md) before enabling AskLens outside local development.

## Compatibility

Current development target:

- Python 3.12+
- Django 6.x
- Django REST Framework 3.17+
- Pydantic v2

Django 5.2 LTS compatibility is not currently claimed. Current package metadata and CI target Django 6.x.
