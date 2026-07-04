# Installation

Django AskLens is currently pre-alpha. Install it into a Django project once the package is available from your chosen source.

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

Include the API URLs if you want the DRF endpoints:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

Run migrations for AskLens-owned audit models:

```bash
python -m django migrate asklens
```

## Minimal settings

```python
DJANGO_ASKLENS = {
    "LLM_BACKEND": "dummy",
    "MAX_ROWS": 500,
    "MAX_JOINS": 2,
    "MAX_METRICS": 5,
    "MAX_GROUP_BY": 3,
    "ALLOW_RAW_SQL": False,
    "SEND_SAMPLE_ROWS_TO_LLM": False,
    "DEFAULT_VISUALIZATION": "table",
}
```

The default API permission class is `rest_framework.permissions.IsAuthenticated`.

## Compatibility

Current development target:

- Python 3.12+
- Django 6.x
- Django REST Framework 3.17+
- Pydantic v2

Django 5.2 LTS compatibility is a future matrix target, not yet proven by CI.
