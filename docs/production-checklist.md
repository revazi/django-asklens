# Production checklist

Use this checklist before enabling AskLens in a production or production-like environment.

AskLens is a data access surface. Configure it as carefully as any reporting, analytics, or admin feature.

## Access gates

- [ ] Set `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]` to permission classes appropriate for your project.
- [ ] Confirm every AskLens route is gated:
  - [ ] `GET /asklens/catalog/`
  - [ ] `GET /asklens/capabilities/`
  - [ ] `POST /asklens/query/`
  - [ ] `GET /asklens/runs/<id>/`
- [ ] Decide who can load the optional packaged frontend.
- [ ] If using the packaged frontend, set `FRONTEND_PERMISSION_CHECK` for selected users.
- [ ] Keep API permissions enabled even when the UI page has its own access gate.

## Request permissions

- [ ] Configure `REQUEST_PERMISSIONS_GETTER` if field/resource visibility is not fully represented by `request.user.get_all_permissions()`.
- [ ] Return only permission strings needed by AskLens.
- [ ] Test representative roles/users against `/asklens/catalog/` and `/asklens/capabilities/`.
- [ ] Confirm unauthorized resources are absent from capabilities and rejected by query validation.

## Resource registration

- [ ] Register only reviewed resources.
- [ ] Register only reviewed fields.
- [ ] Do not auto-expose every Django model or every model field.
- [ ] Give resources and metrics clear labels/descriptions so provider planning has enough semantic context.
- [ ] Keep relation paths within configured `MAX_JOINS`.

## Tenant and row scope

- [ ] Every production resource has a `base_queryset(request)` hook or another reviewed row-scope strategy.
- [ ] `base_queryset(request)` returns no rows for anonymous/unauthorized users.
- [ ] Tests prove users cannot see another tenant's rows.
- [ ] Scope fields are marked with `scope_dimension=True` where useful for capabilities/help guidance.
- [ ] Resources representing the scoped entity itself use `scope_resource=True` where useful.

## Sensitive fields

- [ ] Mark PII, secrets, internal identifiers, notes, and operationally sensitive fields as `sensitive=True` or hide them with `llm_visible=False` / `result_visible=False`.
- [ ] Add `requires_permission` for fields that need explicit access.
- [ ] Test sensitive fields with and without permission.
- [ ] Confirm sensitive fields are absent from capabilities and provider metadata for unauthorized users.
- [ ] Confirm sensitive fields do not appear in result columns/data unless explicitly allowed.

## Limits and query safety

- [ ] Keep `ALLOW_RAW_SQL` disabled. AskLens has no raw SQL execution path.
- [ ] Keep `SEND_SAMPLE_ROWS_TO_LLM` disabled.
- [ ] Set conservative values for:
  - [ ] `MAX_ROWS`
  - [ ] `MAX_JOINS`
  - [ ] `MAX_METRICS`
  - [ ] `MAX_GROUP_BY`
- [ ] Test broad list queries and aggregate queries for acceptable latency.
- [ ] Consider host-project DRF throttling/rate limits.
- [ ] Review database indexes for common filter/group/order fields.

## Live provider configuration

- [ ] Use a secret manager or environment variables for `LLM_API_KEY`.
- [ ] Do not commit provider keys or `.env` files.
- [ ] Set `LLM_TEMPERATURE` to `0` unless you have validated another value.
- [ ] Set an appropriate `LLM_TIMEOUT_SECONDS`.
- [ ] Validate provider behavior in a safe non-production environment that mirrors permissions and tenant scoping.
- [ ] Confirm live provider tests are opt-in and skipped by default in CI.

## Logging

- [ ] Keep `LOG_LLM_IO` disabled in production unless explicitly approved.
- [ ] If provider I/O logging is enabled for debugging, treat logs as sensitive.
- [ ] Confirm logs exclude authorization headers and API keys.
- [ ] Confirm errors do not include tracebacks, secrets, raw credentials, or private row values.

## UI and saved queries

- [ ] Decide whether to use the packaged reference UI or a custom UI.
- [ ] For production product UX, prefer building a custom UI on the API.
- [ ] If saving queries, store project-owned records and submit saved plans back to `/asklens/query/` for revalidation.
- [ ] Do not trust browser-stored plans as an authorization boundary.

## Audit and operations

- [ ] Review `SemanticQueryRun` retention requirements.
- [ ] Confirm successful data queries create audit records.
- [ ] Confirm safe failures create audit records.
- [ ] Confirm help/capabilities responses do not create query-run audit records because they do not query the database.
- [ ] Monitor slow queries and row counts with normal Django/database tooling.

## Final go/no-go

- [ ] Full test suite passes.
- [ ] Live provider validation passes for representative roles.
- [ ] Security checklist is complete.
- [ ] No private data, sample rows, provider payload logs, `.env` files, or credentials are committed.
- [ ] Maintainer/security owner approves the deployment scope.
