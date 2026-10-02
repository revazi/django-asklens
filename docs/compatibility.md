# 0.3.x compatibility boundary

## Scope

Django AskLens remains alpha. This policy governs only the narrow surface named
below for releases in the `0.3.x` line. It is not a 1.0 stability claim, a
promise that every import or serialized shape is stable, or a commitment beyond
`0.3.x`. Security, authorization, scope, privacy, and fail-closed behavior take
priority over preserving unsafe behavior.

The five AskLens documents remain draft, internal, unversioned, and without
schema negotiation. A governed Python entry point does not make every object it
accepts or returns independently governed.

## Exact surface table

| Surface | 0.3.x status | Exact boundary |
| --- | --- | --- |
| Registration and resources | **Governed** | The documented imports and call behavior for `Metric`, `SemanticResource`, `CatalogRegistry`, `default_registry`, `register`, and `get_resource` in `django_asklens` / `django_asklens.catalog`. Explicit semantic names remain separate from private bindings. Undocumented dataclass construction, helper functions, and private attributes are excluded. |
| Trusted execution | **Governed** | `django_asklens.execution.execute_plan(plan, *, request, registry=...)` remains the sole public execution facade. It treats every plan as untrusted and returns a `QueryResult` on success. `QueryResult`'s documented `rows`, `row_count`, `duration_ms`, `limit`, `limit_scope`, `truncated`, and `to_dict()` behavior are governed; direct construction, private attributes, compiler types, and prepared state are not. |
| Public failures | **Governed** | `PublicAskLensError`, `public_error_payload()`, the ten `asklens.*` error-code categories, fixed safe-message behavior, and optional safe JSON pointer are governed. Diagnostic subclasses, causes, and internal messages are not. |
| Host observability | **Governed** | `django_asklens.observability.ObservabilityEvent`, its eight fields and four event-name/status combinations, plus `DJANGO_ASKLENS["OBSERVABILITY_SINK"]` default-off callback behavior are governed as documented in [host controls](host-throttle-and-audit-controls.md). No transport integration is included. |
| Catalog/capability helpers | **Provisional** | `serialize_catalog()`, `build_capabilities()`, catalog item mappings, descriptions, examples, and helper imports may change. Registration trust and member opacity remain mandatory even when these representations change. |
| Planning and result helpers/models | **Provisional** | `django_asklens.planning` and `django_asklens.results`, including Pydantic model constructors, preview validation, presentation, and serialization helpers, are not frozen as a unit. Preview validation never authorizes execution. |
| Settings other than observability | **Provisional** | Existing access, scope, budget, audit, provider, frontend, and MCP settings remain host integration/configuration. Security limits continue to be enforced, but key sets, defaults, and resolution details are not governed by this policy. |
| Audit storage and commands | **Provisional** | `SemanticQueryRun`, migrations, admin presentation, audit payload internals, `check_asklens`, `redact_asklens_audit`, and `purge_asklens_audit` are operational Django surfaces, not governed application APIs. Audit remains authoritative relative to observability. |
| Question/provider orchestration | **Provisional** | `django_asklens.querying`, provider classes, prompts, routing, help, presentation composition, and provider request/response models may change. Data execution must still converge on `execute_plan()`. |
| HTTP/DRF | **Optional, provisional** | View classes, routes, methods, statuses, headers, request serializers, response envelopes, and run-detail representation are not governed by the 0.3.x core boundary. Authentication, opacity, and trusted-facade convergence remain security invariants. |
| MCP | **Optional, provisional** | Framework-neutral helpers, FastMCP wrappers, tool names, arguments, envelopes, and row-omission metadata are not governed. Server-owned identity and trusted-facade convergence remain mandatory. |
| Admin/frontend | **Optional, provisional** | Admin query/audit pages, templates, static behavior, and the reference frontend are not governed. They do not define a second execution route. |
| Five JSON documents and schemas | **Internal, draft** | `catalog`, `query-plan`, `capabilities`, `result`, and `error` documents and their packaged schemas remain unfrozen and unversioned. Accessor imports do not make document shape a governed wire contract. No document version or negotiation field is added. |
| Compiler, ORM bindings, private helpers | **Internal** | Compiler/prepared/context objects, private names, Django paths, SQL, querysets, scope providers, diagnostics, and implementation modules are excluded even if technically importable. |
| Raw SQL, mutation, automatic exposure, client policy | **Unsupported** | Raw SQL, writes, automatic model/field exposure, client-supplied identity/tenant/permission/scope, and execution outside the facade remain unsupported. |

## Change rules within 0.3.x

An ordinary `0.3.z` patch may add compatible optional behavior, fix defects, or
change provisional/internal surfaces. It must not remove a governed import,
change a governed call incompatibly, add event fields or names, reinterpret a
canonical public error, or weaken the trusted-execution invariants.

A security or privacy defect may require an immediate fail-closed change even
when a governed caller observes stricter rejection. The release notes must name
the affected governed behavior, reason, and mitigation without publishing
sensitive exploit details. There is no promise to retain unsafe behavior or add
a compatibility shim.

Incompatibility outside an urgent fail-closed fix belongs in a later minor line
and requires explicit release notes and actionable migration guidance. This
policy provides no fixed deprecation period and makes no compatibility promise
for `0.4.0` or 1.0.

## Upgrade from 0.2.x to 0.3.0

The supported origin is a supported `0.2.x` release; today that means `0.2.0`.
`0.1.0a1` remains a testing artifact and is not an upgrade origin.

1. Back up and test according to host policy, pin the exact reviewed `0.3.0`
   artifact (locally built and digest-verified, or authenticated against an
   immutable publication record), and run the normal Django system check,
   migration-drift check, and application tests for every enabled adapter.
2. No AskLens database migration or data transformation is introduced by this
   scope. Do not generate an empty host migration merely for observability.
3. `OBSERVABILITY_SINK` defaults to `None`; leaving it unset preserves no-hook
   behavior. If enabled, use the exact content-free callback contract and treat
   sink delivery as best-effort metrics/tracing, not audit.
4. Re-test registrations, scope providers, permissions, structural budgets,
   public error handling, and any provisional HTTP/MCP/admin/provider consumer.
   Those adapter and document shapes are not covered by this compatibility
   boundary.
5. Treat every stored, cached, provider-produced, or previously validated plan
   as untrusted. Submit it to the current `execute_plan()` facade so current
   catalog, permissions, scope, and budgets are revalidated.

Because this scope adds no migration, reverting package code does not require a
reverse AskLens migration. That is not a general rollback guarantee: hosts must
remove 0.3-only callback imports/configuration before reverting, and no promise
is made that provisional documents, adapters, provider behavior, or
host-persisted payloads can be mixed across versions.
