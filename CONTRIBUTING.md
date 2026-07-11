# Contributing to Django AskLens

Thanks for your interest in Django AskLens.

Django AskLens is pre-alpha. APIs may change, and contributions should keep the package safe, small, and deterministic.

## Development setup

Use Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync --group dev
```

Run the default checks before opening a pull request:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m django check --settings=tests.test_project.settings
uv run python -m django makemigrations asklens --check --dry-run --settings=tests.test_project.settings
uv run python -m build
uv run twine check dist/*
```

Live LLM tests are opt-in and must not run by default.

## Pull request expectations

- Keep changes focused and reviewable.
- Add or update tests for behavior changes.
- Update docs when API behavior, settings, response shapes, or safety guidance changes.
- Keep default tests offline and deterministic.
- Do not commit `.env` files, API keys, provider payload dumps, local SQLite databases, or sensitive project data.
- For larger design changes, open an issue or discussion before implementation.

## Safety rules

Do not add or weaken safeguards around:

- raw SQL execution from LLM output,
- create/update/delete/mutation behavior,
- automatic exposure of all Django models or fields,
- sending database rows or sample values to providers by default,
- bypassing Django/DRF permissions,
- tenant or row-level scoping through `base_queryset(request)`,
- query limits such as `MAX_ROWS`, `MAX_JOINS`, `MAX_METRICS`, and `MAX_GROUP_BY`.

Provider output is always untrusted. It must parse as structured JSON and pass AskLens validation before any ORM query runs.

## Documentation

Useful starting points:

- [README](README.md)
- [Installation](docs/installation.md)
- [Usage guide](docs/usage.md)
- [Registration API](docs/registration.md)
- [Provider configuration](docs/providers.md)
- [Security checklist](docs/security-checklist.md)

## Typing note

Mypy is not currently an alpha CI gate because the Django/DRF typing baseline is not clean yet. Type annotations are still encouraged for public functions and core helpers.
