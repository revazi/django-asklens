# Security checklist

Use this checklist before enabling AskLens outside local development.

## Catalog and permissions

- [ ] Register only resources users should query.
- [ ] Register only allowed fields; do not auto-expose every model field.
- [ ] Mark PII/secrets/internal fields as `sensitive=True` or hide them with `llm_visible=False` / `result_visible=False`.
- [ ] Use `requires_permission` for fields that need explicit permissions.
- [ ] Review every registered metric for business meaning and data sensitivity.
- [ ] Keep tenant and row-level restrictions in `base_queryset(request)`.
- [ ] Add tests proving each tenant/user only sees rows from the registered resource base queryset.

## Query safety

- [ ] Keep `ALLOW_RAW_SQL` disabled. AskLens has no raw SQL execution path.
- [ ] Keep `SEND_SAMPLE_ROWS_TO_LLM` disabled.
- [ ] Set conservative `MAX_ROWS`, `MAX_JOINS`, `MAX_METRICS`, and `MAX_GROUP_BY` values.
- [ ] Confirm validation rejects unknown resources, fields, metrics, operators, mutation intents, and raw-SQL-like payloads.
- [ ] Confirm all query execution starts from the registered resource base queryset.

## API safety

- [ ] Require authentication for `/asklens/catalog/`, `/asklens/query/`, and `/asklens/runs/<id>/`.
- [ ] Restrict `debug=true` to staff users or a stronger permission gate.
- [ ] Ensure run-detail access is scoped to the requesting user unless a staff/admin policy is intended.
- [ ] Verify configured `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]` gates every AskLens route.
- [ ] Consider DRF throttling/rate limits in host projects.
- [ ] Review audit retention requirements for your environment.

## Provider safety

- [ ] Use `DummyProvider` for tests and deterministic local demos.
- [ ] Do not run live-provider tests by default.
- [ ] Do not include API keys, credentials, `.env` values, sample rows, tenant identifiers, or hidden/sensitive fields in prompts.
- [ ] Treat all provider output as untrusted and require QueryPlan validation before execution.
- [ ] Keep `LOG_LLM_IO` disabled in production unless an approved logging policy covers user questions and permission-scoped schema metadata.

## Deployment safety

- [ ] Consider a read-only database role or replica as defense in depth if your deployment can enforce it outside AskLens.
- [ ] Monitor query volume and slow queries using normal Django/database tooling.
- [ ] Review logs to ensure errors do not include stack traces, secrets, raw credentials, provider payload dumps, or sensitive row values.

AskLens is a data access surface. If in doubt, register less data and add fields/metrics only after review.
