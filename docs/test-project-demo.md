# Runnable complex test project

The source repository includes a synthetic Django test project with complex tenant, role, member, subscription, billing, payment, and schedule models. It is designed for local AskLens integration testing without host-application code or sensitive data. This guide is for a source checkout, not an installed package runtime.

## SQLite frontend and admin first run (start to reset)

This is the shortest browser journey through the synthetic source demo. It uses
the deterministic offline `DummyProvider`, keeps live providers disabled, and
is technical repository evidence only—not production, external usability, or a
security certification.

### 1. Start the small synthetic app

Prerequisites are Python 3.12 or newer, `uv`, and a fresh source checkout. From
the repository root, install the locked development environment, create the
ignored SQLite database, seed the small deterministic dataset, and start the
Django development server:

```bash
uv sync --locked --group dev

DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django migrate --run-syncdb

DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django seed_complex_test_project --size small

DJANGO_ASKLENS_DEMO_LIVE_LLM=0 \
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
uv run python -m django runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/>. The generic Django admin login is the expected
first page; the demo does not add another authentication system.

### 2. Prove row scope first with `facility-owner`

Sign in before using the superuser:

```text
username: `facility-owner`
password: `12admin34`
```

The tenant row scope is immediately visible as North Studio only. It must not
show South Studio. The separate session panel says `Offline dummy plans`. Submit
the exact offline question `Show paid billing revenue by product`; the
deterministic result contains only North-scoped products. Its visible result
boundary shows the effective groups limit and `Truncated: no`. **Raw response**
remains available for the complete unchanged payload, including
`result.result_metadata` (`limit`, `limit_scope`, and `truncated`).

A successful data question creates a metadata-only audit row. Because the
current demo actually uses database audit with `AUDIT_INCLUDE_CONTENT=False`,
the inline audit notice explains that operational run metadata is stored while
the question, complete plan, and result rows are omitted. The stored metadata
includes safe operational fields such as resource, intent, status, row count,
and duration.

### 3. Explore frontend, admin query, and audit roles separately

Log out, then use the synthetic superuser for a separately labeled admin
exploration path:

```text
username: `admin`
password: `12admin34`
```

The superuser scope reads `All demo facilities (superuser)`, so it is not the
identity to use when demonstrating tenant isolation. The three pages have
different roles:

- `/` — frontend data/help page using the same authenticated API and trusted
  execution path;
- `/admin/asklens/asklensquery/` — separate admin query/help page; and
- `/admin/asklens/semanticqueryrun/` — view-only audit page. Its search box
  searches existing audit rows and does not run a query; add, edit, delete, and
  bulk delete are denied even to the superuser.

On the admin query/help page, submit `show me example queries`. The deterministic
offline help response lists suggestions but executes no application-data query
and does not create an audit row. A data question on either query page does
execute through AskLens and creates its normal metadata-only audit row.

### 4. Confirm the safe no-report denial

Log out and sign in with:

```text
username: `no-report`
password: `12admin34`
```

Opening `/` still returns HTTP status `403` with a neutral **Access
unavailable** page. It discloses no resource, reporting grant, membership, or
tenant scope. Use its CSRF-protected **Sign out and switch account** POST action
to return to the existing Django admin login. Diagnose this local synthetic
account from trusted host setup; API denial envelopes remain opaque and route-
level denials still create no AskLens audit row.

### 5. Stop and reset only the synthetic SQLite demo

Press Ctrl-C in the development-server terminal. From the repository root,
remove only this ignored synthetic SQLite file to clear seeded users, domain
data, sessions, and AskLens audit rows:

```bash
rm -f .asklens-test-project.sqlite3
```

Do not reuse the demo credentials or this reset command for a real project. The
command does not remove other databases, virtual environments, or source files.

## What the reference frontend explains

The server-supplied context labels are not authority. They make the current
safe display context visible, while current authorization and row scope are
rechecked for every execution. Empty labels in the packaged frontend default
render no scope section.

Visible result metadata is limited to the existing canonical
`result.result_metadata` values: effective `limit`, `limit_scope` (`rows` or
`groups`), and `truncated` (`yes` or `no`). Truncation applies only to the
current authorized query. `yes` means additional matching rows or groups were
detected beyond the returned result. It does not provide pagination, claim
unscoped completeness, or imply access outside the current scope. **Raw
response remains available** and unchanged.

The inline privacy notice is demo/server-policy-bound. It appears only while the
current demo uses metadata-only database audit with
`AUDIT_INCLUDE_CONTENT=False`; it says operational run metadata is stored while
the question, complete plan, and result rows are omitted. Other audit modes and
full-content opt-in omit that notice, and the packaged frontend makes no global
audit guarantee. API envelopes and trusted execution payloads are unchanged.

## PostgreSQL 18 reference workflow

This synthetic reference app provides internal, draft alpha-candidate evidence only. It is not production or security certification, external pilot evidence, a public specification, or backend-neutral proof. Live providers stay disabled throughout the committed smoke.

Prerequisites:

- Python 3.12 or newer and `uv`;
- Docker Engine with the Docker Compose plugin;
- enough local capacity to run one PostgreSQL 18 container; and
- network access for the initial Python and Chromium downloads.

From a fresh source checkout, the one-command setup is:

```bash
uv sync --locked --group dev && uv run playwright install chromium
```

Run the complete automated smoke with one command:

```bash
bash scripts/reference-demo-smoke.sh
```

The script validates `compose.yaml`, chooses free loopback ports, creates a uniquely named Compose project and named volume, waits for health, verifies the live server is PostgreSQL 18, migrates/syncs and seeds the real synthetic Django app, starts the MCP-enabled ASGI demo, and runs `tests/e2e/reference_demo.py` with Playwright/Chromium. It covers browser login and interaction, permission-scoped catalog and machine capabilities, context scope, list and aggregate execution, typed/canonical JSON values, metadata-only audit records, API routes, real FastMCP Streamable HTTP, default MCP row omission, and fail-closed denial. It then removes only the containers, network, and named volume in that unique Compose project, on success or failure.

For manual exploration, keep the same deterministic PostgreSQL setup and real ASGI/MCP app running until Ctrl-C:

```bash
bash scripts/reference-demo-smoke.sh --manual
```

The command prints its dynamically selected demo and MCP URLs. Ctrl-C stops the server and safely runs `docker compose down --volumes --remove-orphans` for the fixed `django-asklens-reference-demo` project only. If a prior manual run was interrupted before its trap completed, the one-command safe teardown is:

```bash
bash scripts/reference-demo-smoke.sh --teardown
```

The Compose database uses deterministic credentials (`asklens_demo` / `asklens-demo-only`) that are committed and intended only for this synthetic loopback demo. It does not use a developer's existing PostgreSQL server. PostgreSQL data lives in a Docker-managed named volume rather than a host bind mount; the orchestration deliberately removes that project-scoped volume during teardown. Do not reuse these credentials or this Compose configuration for production data.

## SQLite dataset profiles and extended exploration

The first-run path above uses the fast two-facility `small` profile. After
migration, the seed command also supports opt-in `medium` and `large` profiles.
They keep the base demo and add deterministic scaled tenants under slugs such as
`demo-tenant-01`.

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

## Synthetic performance baseline

To run a reproducible local performance baseline, use:

```bash
bash scripts/performance-baseline.sh
```

The workflow is opt-in, runs only in the synthetic test project, seeds with
`medium` by default, and emits a redacted internal-only JSON artifact.

Use smaller CI-safe profiles for quick checks:

```bash
bash scripts/performance-baseline.sh \
  --query-profile compact \
  --iterations 2 \
  --warmups 1 \
  --dataset-profile medium

# commit is captured from HEAD by default:
# --commit can override this if you need a fixed marker
```

See [Synthetic performance baseline](performance-baseline.md) for artifact shape,
command options, and cleanup behavior.

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

Live mode still sends only permission-scoped provider guidance derived from safe catalog and machine-capability metadata. It does not send database rows, sample values, secrets, credentials, or `.env` contents. Provider guidance can include sanitized scope breadth such as whether a resource is visible for one facility or multiple facilities; tenant IDs and names are not sent. The public machine capability document itself contains no resources or human scope guidance. The demo explicitly opts reviewed Django choice fields into safe enum values, labels, and aliases; AskLens does not discover or expose choices automatically. Query-help suggestions are validated so a single-facility user is not given examples that imply comparing or grouping across facilities. `DJANGO_ASKLENS_LIVE_LLM_LOG_IO=1` logs the outbound provider request body, raw provider response, and parsed JSON content at `INFO` level for local tuning. API keys and authorization headers are excluded, but logs can include user questions and permission-scoped provider metadata, so keep them local and temporary.

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

The page uses the packaged, dependency-free AskLens frontend UI with demo-specific starter questions and tenant row-scope context. It shows whether AskLens is using offline dummy plans or a live LLM provider, shows the current user's tenant row scope, loads permission-scoped resources from `/asklens/catalog/`, links to separate machine features at `/asklens/capabilities/`, posts natural-language questions to `/asklens/query/`, and renders returned `result.columns` and `result.data` as table, metric, bar-preview, and raw-response views. Help questions such as `What payment questions can I ask?` return machine capabilities, the visible catalog, and separate suggested questions. You can ask for a count, for example `Give me 10 examples of what I can query`; AskLens caps help suggestions at 10. Live mode generates those suggestions with the configured LLM using only permission-scoped provider guidance. The provider returns question text plus catalog references; AskLens synthesizes and validates a QueryPlan locally for each suggestion and filters invalid suggestions before display. When you click a validated live suggestion in the frontend, the browser sends that plan with the normal query request so AskLens revalidates and executes it directly instead of making another planner LLM call. Suggestions remain pinned after a query runs. The UI shows an explicit loading state while planning/validation/execution is in progress. Useful questions can be saved locally in the browser; saved execution plans are still revalidated by the API before they run. If the provider is disabled or fails validation, the response is clearly labeled as deterministic help or deterministic fallback help. Fallback responses include a safe validation reason so you can see why provider-generated help was not used.

The capabilities and catalog endpoints are metadata only. Machine capabilities contain implementation features and limits without resources or human prose; the catalog contains permission-scoped resources, fields, metrics, and timezones. Human examples and scope-aware guidance are returned separately in query-help responses or used internally for provider prompts. None of these paths returns database rows or sample tenant data. Query results remain tenant-scoped by each resource's explicit context scope provider. Resources and example questions are filtered by the current user's reporting grants and row-scope metadata, so a billing-only user does not see or run package/subscription questions, and a single-facility user is not prompted to compare facilities. Optional API presentation is separate from QueryPlan and cannot affect execution; applications can ignore it or send `"include_presentation": false` to receive only core serialized results. The page uses the same login session and synthetic reporting grants as the API. Staff users without reporting grants cannot load it.

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
  "include_presentation": false
}
```

## Safety notes

- The demo data is synthetic.
- Processor IDs, failure messages, medical notes, and contact fields are intentionally modeled as sensitive and are not registered broadly.
- Tenant isolation is enforced by explicit context-scoped resource providers.
- Field-level sensitive access uses permission strings returned by the configured request-permission getter.
