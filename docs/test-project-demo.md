# Runnable complex test project

The source repository includes a synthetic Django test project with complex tenant, role, member, subscription, billing, payment, and schedule models. It is designed for local AskLens integration testing without host-application code or sensitive data. This guide is for a source checkout, not an installed package runtime.

## Start the admin/demo server

Use the demo settings module so admin, sessions, templates, and a local SQLite database are enabled. For normal admin/frontend testing, use Django's development server:

```bash
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django migrate --run-syncdb

DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django seed_complex_test_project

DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django runserver 127.0.0.1:8000
```

The seed command supports opt-in size profiles. The default `small` profile keeps the fast two-facility demo dataset used by tests. `medium` and `large` keep that base demo and add deterministic scaled tenants under slugs like `demo-tenant-01`.

```bash
# Fast default demo.
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django seed_complex_test_project --size small

# More realistic local dataset: 10 generated tenants × 1,000 members.
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django seed_complex_test_project --size medium

# Stress dataset: 10 generated tenants × 25,000 members.
# This can create millions of related billing/payment rows and may take time.
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django seed_complex_test_project --size large
```

You can override profile dimensions for custom smoke runs:

```bash
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django seed_complex_test_project \
  --size medium \
  --tenant-count 3 \
  --members-per-tenant 500 \
  --months 3 \
  --schedule-weeks 4 \
  --batch-size 1000
```

Seed runs reset previously generated `demo-tenant-*` tenants before reseeding so repeated runs remain deterministic. They do not delete the base North/South demo tenants; `--size small` returns the database to the fast base demo dataset.

By default the demo uses `DummyProvider`, so it makes no network calls and only answers the configured exact demo questions. To use a live OpenAI-compatible provider for free-form planning, set environment variables before starting the server:

```bash
export DJANGO_ASKLENS_DEMO_LIVE_LLM=1
export DJANGO_ASKLENS_LIVE_LLM_API_KEY="$OPENAI_API_KEY"
export DJANGO_ASKLENS_LIVE_LLM_MODEL="gpt-4.1-mini"
# optional for non-OpenAI-compatible gateways:
export DJANGO_ASKLENS_LIVE_LLM_BASE_URL="https://api.openai.com/v1"
# optional local prompt/provider debugging:
export DJANGO_ASKLENS_LIVE_LLM_LOG_IO=1

DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django runserver 127.0.0.1:8000
```

Live mode still sends only permission-scoped schema/catalog/capabilities metadata to the provider. It does not send database rows, sample values, secrets, credentials, or `.env` contents. Capabilities include sanitized scope guidance such as whether a resource is visible for one facility or multiple facilities; tenant IDs and names are not sent to the provider. Query-help suggestions are validated so a single-facility user is not given examples that imply comparing or grouping across facilities. `DJANGO_ASKLENS_LIVE_LLM_LOG_IO=1` logs the outbound provider request body, raw provider response, and parsed JSON content at `INFO` level for local tuning. API keys and authorization headers are excluded, but logs can include user questions and permission-scoped schema/capabilities metadata, so keep them local and temporary.

To run a repeatable live validation matrix through the same AskLens API without starting a browser, use the opt-in command after migrating/seeding:

```bash
DJANGO_ASKLENS_DEMO_LIVE_LLM=1 \
DJANGO_ASKLENS_LIVE_LLM_API_KEY="$OPENAI_API_KEY" \
DJANGO_ASKLENS_LIVE_LLM_MODEL="gpt-4.1-mini" \
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django validate_live_asklens_demo --user admin
```

For Gemini through its OpenAI-compatible endpoint:

```bash
DJANGO_ASKLENS_DEMO_LIVE_LLM=1 \
DJANGO_ASKLENS_LIVE_LLM_API_KEY="$GEMINI_API_KEY" \
DJANGO_ASKLENS_LIVE_LLM_MODEL="gemini-2.5-flash" \
DJANGO_ASKLENS_LIVE_LLM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai" \
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django validate_live_asklens_demo --user admin
```

The command prints safe summaries only: HTTP status, capabilities/query routing, suggestion counts, plan resource/intent, row count, column keys, and safe errors. It does not print API keys or raw environment values. Use `--user north-billing`, `--user mixed-reporter`, or `--all-users` to compare tenant/resource permissions. Pass `--question "..."` one or more times to validate specific prompts.

Open the demo AskLens frontend page:

```text
http://127.0.0.1:8000/
```

Or open Django admin:

```text
http://127.0.0.1:8000/admin/
```

The seed command creates a local demo superuser:

```text
username: admin
password: 12admin34
```

It also creates staff demo users with the same password, deterministic first/last names, Django role groups, `StaffAssignment` rows, and different synthetic tenant/reporting grants:

| Username | Purpose |
| --- | --- |
| `facility-owner` | owner assignment for North Studio only |
| `south-owner` | owner assignment for South Studio only |
| `north-billing` | billing/payment reports for North Studio |
| `south-billing` | billing/payment reports for South Studio |
| `mixed-reporter` | member/PII reports for North Studio and member reports for South Studio |
| `schedule-reporter` | schedule reports for both facilities |
| `support-reporter` | global support-style analytics grant |
| `no-report` | staff login with no reporting grants |

These credentials are for the local synthetic demo project only. Do not reuse them in real projects.

The small seed command creates a richer synthetic dataset for each base facility, including role groups, staff assignments/grants, multiple plans, members, status histories, subscriptions, six months of billing documents, varied billing lines, payment outcomes, marketing campaigns, lead funnel rows, locations, staff shifts, session types, scheduled sessions, bookings/attendance, and support tickets. Medium/large profiles use bulk-created synthetic rows over the same domain tables to validate AskLens behavior on larger tenant and row counts.

The local database file is `.asklens-test-project.sqlite3` and is ignored by git.

## Optional local MCP endpoint

The repository can also expose the runnable demo through a real FastMCP Streamable HTTP endpoint for local MCP-client testing. This uses Uvicorn/ASGI only as a local one-port convenience so `/mcp` and the normal Django demo/admin routes share `127.0.0.1:8000`.

AskLens core and the normal admin/frontend demo do not require ASGI, Uvicorn, or FastMCP. If you are not testing MCP, prefer the `runserver` command above. Host projects can also run an MCP server separately from their normal Django web/admin process.

After migrating and seeding, start the MCP-enabled demo app with:

```bash
DJANGO_ASKLENS_MCP_ENABLED=1 \
DJANGO_ASKLENS_MCP_USERNAME=facility-owner \
uv run uvicorn tests.test_project.demo_asgi:application --host 127.0.0.1 --port 8000
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

Rows remain omitted from MCP tool results unless row return is explicitly enabled:

```bash
DJANGO_ASKLENS_MCP_ALLOW_ROWS=1
```

To expose the optional provider-backed `asklens_query` MCP tool, set:

```bash
DJANGO_ASKLENS_MCP_EXPOSE_QUERY=1
```

Keep the MCP username and permission mapping server-side; do not expose username or permission selection as MCP tool arguments.

## AskLens frontend demo

Open the demo frontend page:

```text
http://127.0.0.1:8000/
```

The page uses the packaged, dependency-free AskLens frontend UI with demo-specific starter questions and tenant row-scope context. It shows whether AskLens is using offline dummy plans or a live LLM provider, shows the current user's tenant row scope, loads permission-scoped guidance from `/asklens/capabilities/`, posts natural-language questions to `/asklens/query/`, and renders returned `columns` and `data` as table, metric, bar-preview, and raw-response views. Help questions such as `What payment questions can I ask?` return capabilities plus suggested questions. You can ask for a count, for example `Give me 10 examples of what I can query`; AskLens caps help suggestions at 10. Live mode generates those suggestions with the configured LLM using only visible capabilities metadata. The provider returns question text plus catalog references; AskLens synthesizes and validates a QueryPlan locally for each suggestion and filters invalid suggestions before display. When you click a validated live suggestion in the frontend, the browser sends that plan with the normal query request so AskLens revalidates and executes it directly instead of making another planner LLM call. Suggestions remain pinned after a query runs. The UI shows an explicit loading state while planning/validation/execution is in progress. Useful questions can be saved locally in the browser; saved execution plans are still revalidated by the API before they run. If the provider is disabled or fails validation, the response is clearly labeled as deterministic help or deterministic fallback help. Fallback responses include a safe validation reason so you can see why provider-generated help was not used.

The capabilities and catalog panels are metadata only: resources, fields, metrics, date fields, generated examples, scope guidance, and limitations visible to the current request. They are not database rows or sample tenant data. Query results remain tenant-scoped by each resource `base_queryset(request)`. Resources and example questions are also filtered by the current user's reporting grants and row-scope metadata, so a billing-only user does not see or run package/subscription questions, and a single-facility user is not prompted to compare facilities. The API visualization value is only a hint for consumers; applications can render the returned data however they prefer or send `"include_visualization": false` to receive serialized data without a visualization hint. The page uses the same login session and synthetic reporting grants as the API. Staff users without reporting grants cannot load it.

## AskLens in admin

Open the AskLens audit model in admin:

```text
http://127.0.0.1:8000/admin/asklens/semanticqueryrun/
```

Open the separate AskLens query admin page:

```text
http://127.0.0.1:8000/admin/asklens/asklensquery/
```

The normal admin search box only searches existing audit records. It does not execute a new query. Use the AskLens query page to ask a data question or a help question such as `show me example queries`. The admin query page uses the same shared planning/help orchestration as `/asklens/query/`, so help requests return examples instead of being forced through the data-query planner. Data questions create normal audit records; help responses do not create query-run audit rows because they do not execute a database query.

## AskLens endpoints

The same demo server exposes:

```text
GET  http://127.0.0.1:8000/asklens/catalog/
GET  http://127.0.0.1:8000/asklens/capabilities/
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

Synthetic staff grants are tenant-scoped through `StaffAssignment` and `StaffGrant` records. The seed command also creates Django auth groups named `AskLens Demo Owners`, `AskLens Demo Staff`, `AskLens Demo Support`, and `AskLens Demo Members` so role membership is visible in admin. Base querysets for reporting resources only include facilities where the request user has the required grant. The seeded `admin` superuser can query all demo facilities for local exploration. The AskLens catalog includes operational resources for facilities, facility owners, members, member contacts, member statuses, subscriptions, billing lines, payment attempts, marketing campaigns, leads, staff shifts, schedule sessions, session bookings, and support tickets. The owner resource is intentionally owner-only so owner-name questions do not return all staff assignments. Capabilities are still permission-scoped, so each user sees only the resources they can query.

## Demo dummy questions

The demo settings include exact `DummyProvider` questions, so `/asklens/query/` can run without an API key or live LLM:

- `Show paid billing revenue by product`
- `Show payment totals by status`
- `List member contact emails`
- `Count member subscriptions by plan and status`
- `Show scheduled capacity by session type`
- `Show campaign spend and conversions by channel`
- `Count leads by source and stage`
- `Show booking attendance by session type`
- `Show staff labor minutes by role`
- `Show support tickets by priority and status`

In live mode, you can also ask free-form questions that map to the visible schema for your current demo user, for example:

- `Show paid billing revenue by product this year`
- `Trend paid billing revenue by month`
- `Show failed payment attempts by billing status`
- `List member contact emails` for users with member PII grants
- `Count member subscriptions by plan and status` for users with package-report grants
- `Show scheduled capacity by session type` for users with schedule-report grants
- `Show booking attendance by session type` for users with schedule-report grants
- `Show staff labor minutes by role` for users with schedule-report grants
- `Count leads by source and stage` for users with member-report grants
- `Show campaign spend and conversions by channel` for users with analytics grants
- `Show support tickets by priority and status` for users with analytics grants

Example JSON request:

```json
{
  "question": "Show paid billing revenue by product"
}
```

Clients that want only serialized data can omit display hints:

```json
{
  "question": "Show paid billing revenue by product",
  "include_visualization": false
}
```

## Safety notes

- The demo data is synthetic.
- Processor IDs, failure messages, medical notes, and contact fields are intentionally modeled as sensitive and are not registered broadly.
- Tenant isolation is enforced in resource `base_queryset(request)` hooks.
- Field-level sensitive access uses permission strings returned by the configured request-permission getter.
