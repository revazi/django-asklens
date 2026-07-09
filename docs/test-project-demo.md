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
uv run python -m django runserver 127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8000/admin/
```

The seed command creates a local demo superuser:

```text
username: admin
password: 12admin34
```

It also creates staff demo users with the same password and different synthetic tenant/reporting grants:

| Username | Purpose |
| --- | --- |
| `facility-owner` | owner assignments for both facilities |
| `north-billing` | billing/payment reports for North Studio |
| `south-billing` | billing/payment reports for South Studio |
| `mixed-reporter` | member/PII reports for North Studio and member reports for South Studio |
| `schedule-reporter` | schedule reports for both facilities |
| `support-reporter` | global support-style analytics grant |
| `no-report` | staff login with no reporting grants |

These credentials are for the local synthetic demo project only. Do not reuse them in real projects.

The local database file is `.asklens-test-project.sqlite3` and is ignored by git.

## AskLens in admin

Open the AskLens audit model in admin:

```text
http://127.0.0.1:8000/admin/asklens/semanticqueryrun/
```

Open the separate AskLens query admin page:

```text
http://127.0.0.1:8000/admin/asklens/asklensquery/
```

The normal admin search box only searches existing audit records. It does not execute a new query. Use the AskLens query page to run a question and see result rows inside the admin UI. Re-running the same successful question for the same admin user reuses the existing audit record instead of creating a duplicate.

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
    "LLM_BACKEND": "dummy",
    "API_PERMISSION_CLASSES": ["tests.test_project.permissions.CanUseComplexAnalytics"],
    "REQUEST_PERMISSIONS_GETTER": "tests.test_project.permissions.get_request_permissions",
    "DUMMY_PLANS": {...},
}
```

Synthetic staff grants are tenant-scoped through `StaffAssignment` and `StaffGrant` records. Base querysets for reporting resources only include facilities where the request user has the required grant. The seeded `admin` superuser can query all demo facilities for local exploration.

## Demo dummy questions

The demo settings include five exact `DummyProvider` questions, so `/asklens/query/` can run without an API key or live LLM:

- `Show paid billing revenue by product`
- `Show payment totals by status`
- `List member contact emails`
- `Count member subscriptions by plan and status`
- `Show scheduled capacity by session type`

Example JSON request:

```json
{
  "question": "Show paid billing revenue by product"
}
```

## Safety notes

- The demo data is synthetic.
- Processor IDs, failure messages, medical notes, and contact fields are intentionally modeled as sensitive and are not registered broadly.
- Tenant isolation is enforced in resource `base_queryset(request)` hooks.
- Field-level sensitive access uses permission strings returned by the configured request-permission getter.
