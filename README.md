# Django AskLens

Django AskLens is a reusable Django + DRF package for safe natural-language querying over explicitly registered Django models.

Status: pre-alpha scaffold. Business logic, model registration, planning, query compilation, LLM providers, and APIs will be added in later approved phases.

## Planned names

- GitHub repository: `django-asklens`
- Python package distribution: `django-asklens`
- Python import package: `django_asklens`
- Django app label: `asklens`

## Safety posture

- No arbitrary SQL execution in the MVP.
- No data mutation features in the MVP.
- No sample database rows sent to LLM providers by default.
- Only explicitly registered models/resources will be queryable.

## Development

Use Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/) for local development.

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The package remains standards-based and setuptools-backed; `uv` is used for contributor workflows, not as a runtime dependency.
