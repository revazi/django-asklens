# Security checklist

Use this checklist before enabling AskLens outside local development.

## Catalog and permissions

- [ ] Register only resources users should query.
- [ ] Register only allowed fields; do not auto-expose every model field.
- [ ] Mark PII/secrets/internal fields as `sensitive=True` or hide them with `llm_visible=False` / `result_visible=False`.
- [ ] Use `requires_permission` for fields that need explicit permissions.
- [ ] Review every registered metric for business meaning and data sensitivity.
- [ ] Require every resource to declare `scope_mode="global"` or `scope_mode="context_scoped"`.
- [ ] Review every `global` resource as intentionally unrestricted across rows.
- [ ] Keep tenant and row-level restrictions in trusted `scope_provider(request)` callables for `context_scoped` resources.
- [ ] Add tests proving missing/invalid scope fails closed and each tenant/user sees only rows from the registered scope queryset.

## Query safety

- [ ] Keep `ALLOW_RAW_SQL` disabled. AskLens has no raw SQL execution path.
- [ ] Keep `SEND_SAMPLE_ROWS_TO_LLM` disabled.
- [ ] Set conservative `MAX_ROWS`, `MAX_JOINS`, `MAX_METRICS`, and `MAX_GROUP_BY` values.
- [ ] Confirm validation rejects unknown resources, fields, metrics, operators, mutation intents, and raw-SQL-like payloads.
- [ ] Pass raw, parsed, saved, or caller-edited plans through `execute_plan()` with the current request. `run_query_plan()` is temporarily retained as a deprecated revalidating wrapper. The compiler and compiled-query executor are internal and are not public APIs.
- [ ] Confirm normal execution starts from the explicitly declared resource scope and test each provider for the current request context.

## API safety

- [ ] Require authentication for `/asklens/catalog/`, `/asklens/query/`, and `/asklens/runs/<id>/`.
- [ ] Restrict `debug=true` to staff users or a stronger permission gate.
- [ ] Ensure run-detail access is scoped to the requesting user unless a staff/admin policy is intended.
- [ ] If using the optional API integration, verify configured `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]` gates every AskLens route.
- [ ] If using the optional API integration, consider DRF throttling/rate limits in host projects.
- [ ] Review audit retention requirements for your environment.

## Provider safety

- [ ] Use `DummyProvider` for tests and deterministic local demos.
- [ ] Do not run live-provider tests by default.
- [ ] Do not include API keys, credentials, `.env` values, sample rows, tenant identifiers, or hidden/sensitive fields in prompts.
- [ ] Treat all provider output as untrusted and require QueryPlan validation before execution.
- [ ] Keep `LOG_LLM_IO` disabled in production unless an approved logging policy covers user questions and permission-scoped schema metadata.

## Audit safety

- [ ] Select `AUDIT_MODE` deliberately and keep `AUDIT_INCLUDE_CONTENT=False` by default.
- [ ] If full content is enabled, define retention, access, redaction, and deletion policy for questions, filters, and plans.
- [ ] Prove rejected plans issue no application-data query; allow at most one metadata insert only in database audit mode.
- [ ] Monitor custom/database sink failures without retrying query execution.

## Deployment safety

- [ ] Consider a read-only database role or replica as defense in depth if your deployment can enforce it outside AskLens.
- [ ] Monitor query volume and slow queries using normal Django/database tooling.
- [ ] Consume stable failures through `error.code` and `error.message`; confirm unknown and unauthorized members both return `asklens.member.unavailable` without catalog or permission detail.
- [ ] Review logs to ensure errors do not include stack traces, secrets, raw credentials, provider payload dumps, or sensitive row values.

AskLens is a data access surface. If in doubt, register less data and add fields/metrics only after review.
