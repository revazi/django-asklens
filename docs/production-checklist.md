# Production checklist

Use this checklist before enabling AskLens in a production or production-like environment.

AskLens is a data access surface. Configure it as carefully as any reporting, analytics, or admin feature. Supported Python execution uses `execute_plan()` (with `run_query_plan()` temporarily retained as a deprecated safe wrapper), and every resource registration must resolve a fail-closed scope policy from an explicit resource mode or the context-only project default. Production-like evaluation must still test host scope providers and operational controls.

## Access gates

- [ ] If using the optional API integration, install `django-asklens[api]` and include `rest_framework` in `INSTALLED_APPS`.
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
- [ ] Register only reviewed semantic fields with explicit private bindings, canonical types, and nullability.
- [ ] Do not auto-expose every Django model or every model field.
- [ ] Confirm catalog, capability, and provider payloads omit bindings, model labels, and permission-token formats.
- [ ] Give resources and metrics clear labels/descriptions so provider planning has enough semantic context.
- [ ] Review each resource's semantic `default_order`; identity-only ordering is acceptable when deliberate.
- [ ] If overriding `row_identity`, confirm the field is concrete, non-null, and unconditionally unique.
- [ ] Keep relation paths within configured `MAX_JOINS`.

## Tenant and row scope

- [ ] Every resource resolves to `global` or `context_scoped`; if configured, `DEFAULT_SCOPE_MODE` is `context_scoped` only.
- [ ] Every `global` resource is deliberately reviewed as unrestricted across rows and declares `scope_mode="global"` individually.
- [ ] Every `context_scoped` resource has a trusted `scope_provider(request)` that returns an unevaluated queryset for the registered model.
- [ ] Scope providers return `none()` for anonymous/unauthorized users unless host policy deliberately permits access.
- [ ] Tests prove missing/invalid scope fails closed and users cannot see another tenant's rows.
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
- [ ] Set conservative values for every structural budget:
  - [ ] `MAX_PLAN_BYTES`
  - [ ] `MAX_FILTERS`
  - [ ] `MAX_SELECTED_FIELDS`
  - [ ] `MAX_ORDER_BY`
  - [ ] `MAX_GROUP_BY`
  - [ ] `MAX_METRICS`
  - [ ] `MAX_JOINS` (maximum relationship-hop depth)
  - [ ] `MAX_RELATIONSHIP_EDGES`
  - [ ] `MAX_IN_VALUES`
  - [ ] `MAX_FILTER_VALUES`
  - [ ] `MAX_ROWS`
  - [ ] `DEFAULT_LIMIT`
- [ ] Test broad list queries and aggregate queries for acceptable latency.
- [ ] Test repeated limited queries for stable ordering and verify `truncated` below, at, and above the effective limit.
- [ ] Configure a database statement timeout appropriate to reporting queries.
- [ ] Configure an end-to-end request timeout.
- [ ] Apply host/API rate and concurrency limits; structural budgets do not bound request volume.
- [ ] Use read-only database credentials or equivalent database policy where practical.
- [ ] Review database indexes for common filter/group/order fields.
- [ ] Monitor duration, errors, rejected budgets, and row/group counts.

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
- [ ] Confirm errors do not include tracebacks, secrets, raw credentials, or sensitive row values.

## UI and saved queries

- [ ] Decide whether to use the packaged reference UI or a custom UI.
- [ ] For production product UX, prefer building a custom UI on the API.
- [ ] If saving queries, store project-owned records and submit saved plans back to `/asklens/query/` for revalidation.
- [ ] Do not trust browser-stored plans as an authorization boundary.

## Audit and operations

- [ ] Choose `AUDIT_MODE`: `database` (default), `disabled`, or `custom`; configure a callable/import-path `AUDIT_SINK` for custom mode.
- [ ] Confirm successful and rejected data-query attempts reach the selected sink exactly once. Database rejection auditing may issue one metadata-only `INSERT`; it must not issue an application-data query.
- [ ] Confirm disabled/custom non-database auditing adds zero SQL to rejected plans.
- [ ] Keep `AUDIT_INCLUDE_CONTENT=False` unless storing questions, filter values, and complete validated plans has an explicit retention, access, redaction, and deletion policy.
- [ ] Confirm help/capabilities responses do not create query-run audit records because they do not execute a data query.
- [ ] Monitor audit-sink failures, slow queries, and row counts with normal Django/database tooling.

## Final go/no-go

- [ ] Full test suite passes.
- [ ] Live provider validation passes for representative roles.
- [ ] Security checklist is complete.
- [ ] No sensitive data, sample rows, provider payload logs, `.env` files, or credentials are committed.
- [ ] Maintainer/security owner approves the deployment scope.
