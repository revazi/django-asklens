# Runnable complex test project

The source repository includes a synthetic Django test project with complex tenant, role, member, subscription, billing, payment, and schedule models. It is designed for local AskLens integration testing without private project code or data. This guide is for a source checkout, not an installed package runtime.

## Start the admin/demo server

Use the demo settings module so admin, sessions, templates, and a local SQLite database are enabled.

```bash
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django migrate --run-syncdb

DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django seed_complex_test_project

DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django createsuperuser

DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django runserver 127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8000/admin/
```

The local database file is `.asklens-test-project.sqlite3` and is ignored by git.

## AskLens endpoints

The same demo server exposes:

```text
GET  http://127.0.0.1:8000/asklens/catalog/
POST http://127.0.0.1:8000/asklens/query/
GET  http://127.0.0.1:8000/asklens/runs/<id>/
```

The demo settings register the complex resources at startup and use:

```python
DJANGO_ASKLENS = {
    "API_PERMISSION_CLASSES": ["tests.test_project.permissions.CanUseComplexAnalytics"],
    "REQUEST_PERMISSIONS_GETTER": "tests.test_project.permissions.get_request_permissions",
}
```

Synthetic staff grants are tenant-scoped through `StaffAssignment` and `StaffGrant` records. Base querysets for reporting resources only include facilities where the request user has the required grant. Staff users can query all demo facilities for local exploration.

## Safety notes

- The demo data is synthetic.
- Processor IDs, failure messages, medical notes, and contact fields are intentionally modeled as sensitive and are not registered broadly.
- Tenant isolation is enforced in resource `base_queryset(request)` hooks.
- Field-level sensitive access uses permission strings returned by the configured request-permission getter.
