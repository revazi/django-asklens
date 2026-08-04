# Changelog

All notable changes to Django AskLens will be documented here.

The project is alpha and APIs may change before a stable release.

## Unreleased

### Added

- Began the R1 trusted-execution boundary with public `execute_plan(plan, *, request, registry=...)`, which treats mappings and existing `QueryPlan` objects as untrusted and repeats current permission, catalog, limit, and request-scope validation before ORM execution.
- Added stable namespaced public errors for parse, unavailable-member, plan, authorization, scope, budget, binding, compilation, execution, and provider failures.
- Added server-owned audit modes: `database` (default), `disabled`, and `custom`, with an optional callable `AUDIT_SINK` for non-database operational events.
- Added required resource `scope_mode="global" | "context_scoped"` registration and trusted `scope_provider=...` support.
- Added configurable structural budgets for 64 KiB plan payloads, filters, selected/order/group/metric terms, relationship depth and unique edges, per-`in` and total filter values, returned rows/groups, and the default result limit.
- Added semantic resource `default_order` plus private `row_identity` registration, defaulting to the model primary key.
- Added `DEFAULT_SCOPE_MODE="context_scoped"` for projects that want to configure the safe resource mode once while keeping every global resource explicit.
- Added stable public semantic field keys with required private Django `binding`, canonical `type`, and `nullable` registration metadata.
- Added trusted metric `binding`, `result_type`, `requires_permission`, `cardinality_policy`, and optional private `distinct_key` registration metadata.
- Added explicit enum definitions with string/integer canonical values, safe labels, and accepted aliases; enum metadata is catalog-visible only when deliberately registered.
- Added a canonical per-type filter-operator matrix to permission-scoped capabilities and result-column nullability metadata.
- Added required explicit server-owned IANA timezone registration for every resource; the timezone is safe catalog/capability metadata but cannot be supplied by a plan.
- Added optional presentation envelopes using `{"kind": "table|metric|bar|line|pie", ...}` outside QueryPlan and normalized them only against completed result columns.
- Added five packaged Draft 2020-12 JSON Schemas and Python accessors for the one current internal catalog, query-plan, capabilities, result, and error shape; the schemas remain draft and unfrozen.
- Added a language-neutral synthetic conformance corpus with explicit positive, structural, member/scope/security, budget, semantic, ordering/truncation, and serialization cases plus trusted SQLite replay.
- Added required PostgreSQL 15/18 database-sensitive and conformance CI coverage with a development-only psycopg driver.
- Added a source-checkout PostgreSQL 18 Compose reference database and one-command Playwright/Chromium smoke over the real synthetic ASGI/API/FastMCP demo, with project-scoped teardown and live providers disabled.
- Added isolated source-wheel core/API/MCP install and published-`0.1.0a1` replacement evidence. It leaves the repository version unchanged and performs no upload, tag, or release.

### Changed

- Shared API/admin/MCP/provider orchestration now delegates data execution to `execute_plan()`.
- `run_query_plan()` is a deprecated compatibility wrapper that requires the current request and revalidates plans instead of trusting prior validation.
- ORM compilation now consumes a private, non-serializable prepared representation bound to the current execution context and resolved resource queryset.
- AskLens query-plan failures in the API and MCP helpers now expose an `error` object containing only `code`, safe `message`, and an optional safe JSON `pointer`, replacing raw diagnostic strings and transport-specific `error_category` values.
- Invalid `/asklens/query/` request bodies now return `asklens.parse.invalid` without exposing DRF serializer field details.
- Omitted plan limits now use the current `DEFAULT_LIMIT` (capped by `MAX_ROWS`) instead of acting as a fixed protocol constant; explicit limits require positive JSON integers rather than coercing booleans, floats, or numeric strings, and repeated meaningless structural references are rejected.
- List ordering uses semantic defaults when needed and always appends a missing private identity tie-breaker; grouped ordering appends missing group keys and nulls sort last.
- Result metadata replaces non-definitive `limit_reached` with accurate `truncated`; list/grouped queries fetch `limit + 1`, while ungrouped aggregates have effective limit one.
- Database auditing now stores operational resource/intent/status/error/row-count/duration metadata by default; questions, filter values, and complete plans require explicit `AUDIT_INCLUDE_CONTENT=True` opt-in.
- Resource registration no longer has an implicit default-manager scope. Migrate `base_queryset=visible_rows` to a context-scoped registration with `scope_provider=visible_rows`; intentionally unrestricted resources must declare `scope_mode="global"`. Without a configured `DEFAULT_SCOPE_MODE`, omission still fails registration.
- Field registration no longer interprets public mapping keys as Django paths. Every field now declares its private `__`-separated binding and explicit public type/nullability; changing a binding does not change the public plan.
- QueryPlan metrics now contain only `{"metric": "registered_name"}`. Operations, backing fields, result types, permissions, distinctness, and relationship policy are resolved from trusted registration; 0.1 `name`/`op`/`field` metric objects and the legacy field-level `metric=True` flag are rejected with migration guidance.
- Every filter now requires a non-null `value`. Filter validation enforces canonical JSON value types before scope resolution: decimal inputs remain finite strings, floats remain finite JSON numbers, UUIDs normalize canonically, and enum values resolve only through explicit values/aliases. Django `choices` labels are no longer inferred as input aliases.
- `neq` explicitly excludes null rows. Empty ungrouped aggregates return one row (`count=0`; `sum`/`avg`/`min`/`max=null`), while empty grouped aggregates return no rows.
- Result serialization now preserves decimal strings, verifies canonical runtime types, declared columns, nullability, and registered enum outputs, and rejects unsupported objects instead of stringifying them. Callers that directly construct the alpha `ResultColumn` helper must add `nullable=True|False`; the legacy broad `number` label is no longer canonical.
- Decimal aggregate metric results now use canonical minimal plain-decimal strings: insignificant fractional trailing zeros are removed, decimal zero becomes `"0"`, and exponent notation is never emitted. Scalar decimal field results continue preserving scale.
- The compact provider response schema now correctly requests semantic-name-only metric objects.
- Temporal filters now require strict ISO dates, offset-free local times, and offset-bearing RFC 3339 datetimes. Date ranges are inclusive, datetime ranges are half-open, relative filters use the injected aware clock with an exclusive upper bound at `now`, rolling days are exact 24-hour durations, calendar months use resource-local wall time with month-end/DST handling, and date buckets use the explicit resource timezone with Monday week starts.
- Provider and dummy responses now separate `query_plan` from optional `presentation`. API/MCP callers use `presentation` and `include_presentation`; presentation cannot change authorization, scope, compilation, ordering, limits, or returned values.
- Machine capabilities now contain only supported intents, filter logic, canonical type/operator rules, time grains, structural limits, features, aggregate policies, and backend restrictions. Permission-scoped resources remain in the separate catalog; human guidance and examples remain in query-help/provider paths.

### Removed

- Removed `compile_query_plan`, `CompiledQuery`, and `execute_query` from public package exports. Python callers must use `execute_plan()`; there is no supported unsafe execution API.
- Removed the `include_internal=True` catalog option; public catalog serialization no longer exposes Django model labels.
- Removed the standalone `create_query_run` compatibility export so supported execution cannot bypass the configured privacy-aware audit policy/sink.
- Removed `visualization` from QueryPlan, compiler state, core `QueryResult`, and core result serialization, along with the inert `DEFAULT_VISUALIZATION` setting. Legacy plan input is rejected with pointer `/visualization`; migrate it to the separate presentation envelope.

### Security

- Directly constructed `QueryPlan` objects can no longer bypass current field permissions or configured plan limits through the public facade or compatibility runner.
- Unknown and unauthorized resources, fields, and metrics now share the same public `asklens.member.unavailable` code and message; internal member names, permission tokens, scope failures, compiler causes, and database causes are not included in public execution errors.
- Added regression evidence that preview validation cannot authorize later execution and that ordinary plans are revalidated against current resource, field, metric, policy, catalog, identity, and request scope.
- Added adapter-convergence evidence for core provider orchestration, API, admin, and MCP execution through `execute_plan()`; the packaged frontend remains an API client rather than an independent execution path.
- Rejected plans perform zero application-data queries. Database audit mode performs at most one metadata-only insert; disabled/custom non-database modes add zero SQL. Audit-sink failure cannot trigger rejected-plan execution or hide a successful result.
- Missing scope declarations fail registration unless the safe `context_scoped` project default is configured. `DEFAULT_SCOPE_MODE="global"` is rejected. Missing request context, absent/invalid/evaluated/wrong-model scope results, and scope-provider failures reject with `asklens.scope.unavailable` instead of broadening to the default manager.
- Public catalogs, capabilities, and provider metadata omit private Django field and metric bindings, metric operations/distinct keys, model labels, and permission-token formats while continuing to enforce registration and current-request permissions.
- To-many metrics now fail closed by default. Only explicit one-grain `count_rows` and private-key `count_distinct` registrations are accepted; numeric to-many aggregates, unsafe keys, plan-level fanout, and independent relationship paths reject before application-data SQL.
- Every over-budget structural dimension rejects with `asklens.budget.exceeded` before scope resolution or application-data SQL; malformed UTF-8 byte plans return a typed parse error.
- Unsupported type/operator pairs, invalid scalar types, and unknown enum inputs reject with `asklens.plan.invalid` before scope resolution or application-data SQL. Unsupported result objects fail with the safe `asklens.execute.failed` category.
- The PostgreSQL reference smoke proves server-owned MCP identity, host-and-request row-return gating, metadata-only audit records, tenant-scoped list/aggregate behavior, and fail-closed no-report access using synthetic data. This is internal technical evidence, not production certification or an independent security audit.

## 0.1.0a1 — 2026-07-19

This alpha collects the post-`0.1.0a0` core/API split, Django 5.2 compatibility work, and MCP integration surface.

### Added

- Core Python API guide for using AskLens without Django REST Framework.
- Framework-neutral MCP adapter helpers and `AskLensMCPToolSet` wrapper for capabilities, plan validation, safe plan execution, and optional AskLens-managed question orchestration.
- Optional `mcp` extra with a FastMCP bridge and local demo ASGI `/mcp` endpoint for source checkouts.
- Compact MCP discovery helpers for QueryPlan schema and per-resource metadata.
- MCP integration examples, including generic wrapper registration and a concrete test-project fake MCP server flow.
- CI wheel smoke coverage for core, optional API, and optional MCP installs across the supported Django lines.

### Changed

- Moved shared query/help orchestration, request permission helpers, and admin access checks out of DRF-coupled API modules.
- Made Django REST Framework an optional `api` extra while keeping core catalog, planning, validation, compilation, execution, admin imports, and result serialization usable without importing DRF.
- Expanded supported Django versions to include Django 5.2 LTS alongside Django 6.x, with CI coverage for both lines.
- Clarified that the ASGI/Uvicorn MCP demo is a local one-port convenience, not a production deployment requirement.

### Security

- MCP plan validation and execution revalidate client-produced plans before ORM execution.
- MCP result rows remain omitted by default and require both explicit tool input and `MCP_ALLOW_ROW_RETURN=True`.
- MCP row-return payloads are capped with `MCP_MAX_RETURNED_ROWS` metadata.
- MCP wrappers derive request context server-side instead of accepting client-controlled usernames or permission strings.

## 0.1.0a0 — 2026-07-19

### Added

- Minimal Django reusable app scaffold and test harness.
- Explicit semantic catalog registration with field and metric metadata.
- Strict Pydantic QueryPlan schema and catalog validation.
- ORM-only compiler and executor for read-only list and aggregate queries.
- Deterministic planner/provider flow with `DummyProvider`.
- DRF catalog/query/run endpoints and `SemanticQueryRun` audit model.
- Frontend-agnostic result serialization and visualization-hint normalization.
- Public-alpha documentation drafts and deterministic evaluation fixtures.
- Multi-tenant API security tests covering base-queryset scoping, permission-gated fields, route permission gates, and permission-scoped catalog/planner metadata.
- OpenAI-compatible provider using Python stdlib HTTP.
- Mocked and opt-in live provider tests.
- Public security, production-readiness, provider, custom-UI, and multi-tenant guidance for alpha adopters.
- Configurable request-permission getter for projects with role-based or staff permission systems outside Django's default `user.get_all_permissions()`.
- Runnable complex test project with admin-enabled demo settings, synthetic tenant-scoped grants, and complex member/subscription/billing/payment/session resources.
- Dedicated Django admin AskLens query page that runs the same shared query/help orchestration as the DRF API and displays result rows or capability guidance.
- Demo seed command creates a local admin superuser, staff users with varied synthetic tenant/reporting grants, and richer per-facility synthetic data.
- Packaged optional AskLens frontend page that calls the catalog/query APIs and displays returned data with switchable client-side views.
- Tenant-scoped demo permission tokens for complex test-project grants, including regression coverage for facility-level row separation.
- Resource-level permission scoping for catalog visibility and plan validation, plus permission-filtered demo questions.
- Environment-driven live OpenAI-compatible planner mode for the runnable complex demo project.
- Permission-scoped capabilities endpoint, semantic capability-question routing, LLM-generated query suggestions from visible capabilities, and demo guidance for "what can I query?" UX.
- Planner guidance and validation normalization for date-bucket visualization aliases such as `start_date_month`.
- Opt-in demo validation management command for live LLM smoke checks across seeded users/questions.
- Size profiles for the complex demo seed command, including medium/large bulk-generated tenant/member/billing datasets.
- Additional realistic demo tables and AskLens resources for marketing campaigns, leads, bookings/attendance, staff shifts, and support tickets.
- Sanitized capability scope guidance and validation so query-help suggestions do not imply multi-tenant access for single-scope users.
- Suppressed single-scope entity examples such as plural facility-list suggestions for users scoped to one facility.
- Added schema-agnostic `scope_resource` and `scope_dimension` registration metadata so scope-aware help does not depend on tenant/facility/account naming.
- Seeded demo role groups, user full names, explicit owner grants, and an owner-only facility owners resource for owner lookup questions.
- Added a regression-tested demo permission/resource matrix; owners see all resources, mixed member reporters no longer receive billing resources, and owner email requires a staff-PII grant.
- Added `examples_enabled=False` for queryable helper resources that should not dominate deterministic “what can I query?” suggestions, clarified LLM-vs-fallback help labels in the demo UI, allowed help requests such as “give me 10 examples” to return up to 10 validated suggestions, canonicalized provider resource/field/metric labels, and surfaced safe fallback reasons when live QueryHelp fails validation.
- Tolerated missing `visualization.y` for unambiguous single-metric aggregate plans by inferring the requested metric, and ignored accidental table visualization axes, reducing live-LLM failures for generated metric/table questions.
- Added a unified live provider response path for `/asklens/query/`: one LLM call now decides whether to return a data `QueryPlan` or capability `QueryHelp`, using permission-scoped capabilities metadata once. QueryHelp suggestions use provider-generated questions plus catalog references; AskLens synthesizes and validates executable QueryPlans locally, filters invalid suggestions before display, and the demo can execute clicked suggestions with the validated plan without making another LLM call.
- Added opt-in `LOG_LLM_IO` provider logging for local live-LLM debugging; logs include sanitized provider request/response payloads without API keys or authorization headers.
- Added `response_type: "query"` and `result_metadata` to successful data responses so API clients can distinguish query/help responses and display alpha-safe limit guidance.
- Added opt-in provider prompt resource shortlisting with alpha default disabled (`PROMPT_RESOURCE_SHORTLIST_LIMIT=0`) so providers see all visible resources in compact form unless projects opt into prompt reduction.
- Added deterministic offline help improvements: generated suggestions include catalog references and locally validated plans when possible.
- Added safer provider-help fallback diagnostics that avoid exposing raw validation details or provider payloads.
- Added GitHub Actions CI for Python 3.12 and 3.13 with tests, Ruff lint/format checks, Django checks, migration drift checks, package build/Twine checks, artifact guards, and wheel-install smoke testing.

### Security

- No raw SQL execution path.
- No write/update/delete query intents.
- No sample database rows sent to providers by default.
- Sensitive and hidden fields excluded from default planner catalog serialization.
- Crafted provider plans cannot use permission-gated tenant fields without the required configured permission string.
- Catalog and planner prompt metadata are scoped to configured request permissions.
- Complex tenant tests prove resource base querysets restrict rows to facilities where the user has the required synthetic reporting grant.
- Live provider errors avoid exposing API keys or raw credentials.
