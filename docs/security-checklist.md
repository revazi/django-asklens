# Security checklist

Use this checklist before enabling AskLens outside local development.

## Catalog and permissions

- [ ] Register only resources users should query.
- [ ] Register only allowed semantic fields; give each an explicit private Django binding, canonical type, and nullability.
- [ ] Confirm public catalogs, capabilities, and provider prompts contain no Django bindings, model labels, or permission-token formats.
- [ ] Mark PII/secrets/internal fields as `sensitive=True` or hide them with `llm_visible=False` / `result_visible=False`.
- [ ] Use `requires_permission` for fields that need explicit permissions.
- [ ] Review every registered metric's private binding, result type, permission, and relationship-cardinality policy for business meaning and data sensitivity.
- [ ] Require an explicit server-owned IANA timezone on every resource and test temporal boundaries without client or Django-setting fallback.
- [ ] Keep the default `to_one_only` policy unless an explicit one-grain `count_rows` or private-key `count_distinct` metric has been reviewed; never use a numeric to-many aggregate.
- [ ] Require every resource to resolve to `global` or `context_scoped`; if using `DEFAULT_SCOPE_MODE`, keep it `context_scoped`.
- [ ] Review every `global` resource as intentionally unrestricted across rows and declare it explicitly on that resource.
- [ ] Keep tenant and row-level restrictions in trusted `scope_provider(request)` callables for `context_scoped` resources.
- [ ] Add tests proving missing/invalid scope fails closed and each tenant/user sees only rows from the registered scope queryset.

## Query safety

- [ ] Keep `ALLOW_RAW_SQL` disabled. AskLens has no raw SQL execution path.
- [ ] Keep `SEND_SAMPLE_ROWS_TO_LLM` disabled.
- [ ] Set conservative values for plan bytes, filters, selected fields, ordering, groups, metrics, relationship depth/edges, `in` values, total filter values, returned rows/groups, and the default limit. See the complete setting list in the production checklist.
- [ ] Confirm validation rejects unknown resources, fields, metrics, operators, mutation intents, and raw-SQL-like payloads.
- [ ] Pass raw, parsed, saved, or caller-edited plans through `execute_plan()` with the current request. `run_query_plan()` is temporarily retained as a deprecated revalidating wrapper. The compiler and compiled-query executor are internal and are not public APIs.
- [ ] Confirm normal execution starts from the explicitly declared resource scope and test each provider for the current request context.
- [ ] Review semantic default ordering and any private row-identity override; alternate identities must be concrete, non-null, and unconditionally unique.
- [ ] Verify repeated limited queries are stable and `truncated` is true only when another row/group exists.

## API safety

- [ ] Require authentication for `/asklens/catalog/`, `/asklens/query/`, and `/asklens/runs/<id>/`.
- [ ] Restrict `debug=true` to staff users or a stronger permission gate.
- [ ] Ensure run-detail access is scoped to the requesting user unless a staff/admin policy is intended.
- [ ] If using the optional API integration, verify configured `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]` gates every AskLens route.
- [ ] If using the optional API integration, configure host-side DRF/proxy throttles before execution and confirm throttled requests never reach AskLens facade logic.
  See [Host throttling and audit controls](host-throttle-and-audit-controls.md).
- [ ] Review audit retention requirements for your environment.

## Provider safety

- [ ] Use `DummyProvider` for tests and deterministic local demos.
- [ ] Do not run live-provider tests by default.
- [ ] Do not include API keys, credentials, `.env` values, sample rows, tenant identifiers, or hidden/sensitive fields in prompts.
- [ ] Treat all provider output as untrusted and require QueryPlan validation before execution.
- [ ] Keep `LOG_LLM_IO` disabled in production unless an approved logging policy covers user questions and permission-scoped schema metadata.

## Audit safety

- [ ] Select `AUDIT_MODE` deliberately and keep `AUDIT_INCLUDE_CONTENT=False` by default.
- [ ] Define retention, access, redaction, and deletion policy even for metadata-only records; AskLens does not schedule lifecycle work or automatically expire audit rows.
- [ ] Preview built-in database content redaction with `redact_asklens_audit --before <strict-aware-RFC3339>` and review its point-in-time count before explicitly adding `--execute`; grant update permission only on the selected alias used for execution.
- [ ] Confirm the command clears `question` and `plan` only, prints no row IDs/content, never invokes custom sinks, and is not treated as purge or complete user/tenant deletion handling.
- [ ] If full content is enabled, separately justify and test ingestion/display/export redaction, tightly restricted access, scheduled deletion, backup/replica deletion handling, and every custom sink for questions, filters, and plans. Custom sinks, backups, and replicas remain host-owned.
- [ ] Prove rejected plans issue no application-data query; allow at most one metadata insert only in database audit mode.
- [ ] Monitor custom/database sink failures without retrying query execution.

## Deployment safety

- [ ] Configure database statement and request timeouts plus host rate/concurrency limits; structural budgets do not bound scans, runtime, or request volume completely.
- [ ] Ensure MCP and Python entry points also enforce equivalent host limits and auth/rate controls before calling AskLens helpers.
- [ ] No mandatory OpenTelemetry/Prometheus/queue/cache service dependencies are required for this alpha hardening scope.
- [ ] Use a read-only database role or replica as defense in depth if your deployment can enforce it outside AskLens.
- [ ] Monitor query volume, budget rejections, and slow queries using normal Django/database tooling.
- [ ] Consume stable failures through `error.code` and `error.message`; confirm unknown and unauthorized members both return `asklens.member.unavailable` without catalog or permission detail.
- [ ] Review logs to ensure errors do not include stack traces, secrets, raw credentials, provider payload dumps, or sensitive row values.
- [ ] Run point-in-time dependency evidence as a metadata check:
  ```bash
  uv audit --locked --preview-features audit-command
  ```
  This is dependency metadata evidence for the current lock only; it is not an independent security audit, SBOM, or production certification claim.
- [ ] Remediation policy for this control:
  - fixed vulnerabilities must be upgraded or replaced immediately when feasible.
  - a temporary exception is only allowed when no fix or replacement is available after review.
    - document advisory ID;
    - document evidence of no fix/replacement at decision time;
    - document mitigation used meanwhile;
    - assign explicit owner and explicit review/expiry date;
    - record maintainer decision for the exception.
  - no ignore/allowlist entries are added in this tranche.

AskLens is a data access surface. If in doubt, register less data and add fields/metrics only after review.
