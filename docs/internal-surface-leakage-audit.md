# Internal metadata, result, and error leakage audit

## Status and scope

This is the exact-current #83 field audit for the Django 0.2 target at baseline
`c6d54e465d4631a9848744443b190e1657dc59e0`. It inventories the five internal
documents and the supported HTTP, MCP, provider/guidance, and audit-detail
surfaces that embed or adapt them.

The audit is **internal, draft, and unfrozen**. It is not a public specification,
not a compatibility promise, not evidence of backend neutrality, and not an
independent security review. It does not freeze an adapter shape, approve a
release, or authorize runtime, schema, fixture, audit-policy, or API changes.

The question is narrow: does a current outward-facing or provider-facing field
reveal server-owned private backend or policy data such as bindings, model/table
names, QuerySets, ORM expressions, permission tokens, tenant or scope
identifiers, credentials, diagnostics, provider payloads, or unauthorized rows?
The audit also classifies backend-derived and adapter-only fields so that a thin
wrapper is not mislabeled as a leak or as an exact internal document.

## Classification rules

- **Exact internal document** — one of catalog, capabilities, query-plan,
  result, or error, validated against the current closed internal shape.
- **HTTP adapter wrapper** — routing, orchestration, audit-reference, display,
  or transport metadata outside an exact document.
- **MCP adapter wrapper** — tool-state and row-return metadata outside an exact
  document.
- **Normalized semantic metadata** — a public semantic fact derived from trusted
  registration or execution without exposing its private Django representation.
- **Sanitized human guidance** — non-machine prose or coarse scope guidance that
  omits policy tokens and scope identifiers.
- **Server-owned operational metadata** — bounded execution/audit facts such as
  status, duration, row count, timestamp, and audit record ID.
- **Caller-supplied echo** — a question or caller-provided validated public plan
  returned to the same caller. A provider-generated plan is validated public
  orchestration output rather than caller input. Both can still contain
  privacy-sensitive filter values, but neither is server-owned backend/policy
  metadata.
- **Explicit content opt-in** — question/full-plan audit retention and display
  enabled only by current host configuration and authorization.

Labels, descriptions, synonyms, enum values/aliases, semantic keys, and example
guidance are safe only to the extent the host deliberately registered them as
public metadata. AskLens does not infer them from database rows. A host must not
place secrets, real row samples, or sensitive identifiers in those fields.

## Exact internal documents

| ID | Surface and emitted fields | Classification | Private or derived inputs and treatment | Focused evidence |
| --- | --- | --- | --- | --- |
| SURFACE-01 | Catalog: top-level `resources`; each resource has `name`, `label`, `description`, `synonyms`, `default_date_field`, `timezone`, `fields`, `metrics`, and optional `scope_resource`, `examples_enabled`, `default_order`; fields have semantic `name`, `label`, `type`, `nullable`, `relation_depth`, and optional enum/visibility guidance; metrics have `name`, `label`, `result_type`. | Exact internal document plus Normalized semantic metadata. | [`resources.py`](../django_asklens/catalog/resources.py) serializes explicit host metadata. Private field/metric bindings, relationship paths/edges, model, row identity, scope provider/mode, distinct key, cardinality policy, and permission requirements remain in frozen registration objects and are not copied. `relation_depth` is a normalized relationship-budget count, not a path. | [`tests/catalog/test_registry.py`](../tests/catalog/test_registry.py) checks binding independence, permission filtering, explicit enums, and schema-agnostic scope metadata; [`tests/contracts/test_schemas.py`](../tests/contracts/test_schemas.py) rejects private properties. |
| SURFACE-02 | Machine capabilities: `intents`, `filter_logic`, `types`, `time_grains`, `limits`, `features`, `aggregate_policies`, `backend_restrictions`. | Exact internal document plus Normalized semantic metadata. | [`capabilities.py`](../django_asklens/catalog/capabilities.py) emits implementation-wide types/operators/limits and explicit supported/unsupported facts. It accepts no permission argument and includes no resources, labels, descriptions, examples, scope guidance, models, or bindings. Current `backend_restrictions` is an empty list. | [`tests/catalog/test_capabilities.py`](../tests/catalog/test_capabilities.py): `test_machine_capabilities_exclude_catalog_and_human_guidance`; [`tests/contracts/test_schemas.py`](../tests/contracts/test_schemas.py). |
| SURFACE-03 | Query plan: `resource`, `intent`, and optional `filters`, `select`, `group_by`, `metrics`, `order_by`, `limit`; nested members contain semantic fields/metrics and bounded values only. | Exact internal document; caller/provider input, never authority. | [`_models.py`](../django_asklens/contracts/_models.py) and the closed query-plan schema have no identity, permissions, tenant, scope token, clock, binding, operation-selected metric backing, audit configuration, SQL, or presentation. Validation and current-context execution are separate. | [`tests/contracts/test_schemas.py`](../tests/contracts/test_schemas.py); [`tests/execution/test_untrusted_plan_generative.py`](../tests/execution/test_untrusted_plan_generative.py) checks hostile private/policy markers and safe rejection. |
| SURFACE-04 | Result: `columns`, `data`, `row_count`, optional `empty`, `duration_ms`, and `result_metadata`; columns contain `key`, `label`, `type`, `nullable`; limit metadata contains `limit`, `limit_scope`, `truncated`. | Exact internal document; columns/metadata are normalized, while `data` is the authorized query result. | [`serialization.py`](../django_asklens/results/serialization.py) requires exact semantic row/column key agreement and canonical typed cells. Private ORM aliases and bindings are replaced by semantic result keys. Unknown objects, unregistered enums, non-finite numbers, and nullability mismatches fail rather than being stringified. Returning authorized rows is intended execution output, not metadata leakage; MCP applies a separate default-deny row policy. | [`tests/results/test_serialization.py`](../tests/results/test_serialization.py); exact result/schema checks in [`tests/contracts/test_schemas.py`](../tests/contracts/test_schemas.py). |
| SURFACE-05 | Error: `code`, safe `message`, and optional bounded JSON `pointer`. | Exact internal document. | [`exceptions.py`](../django_asklens/exceptions.py) maps internal causes to fixed public metadata. Diagnostic messages, tracebacks, malformed pointers, unavailable member names, provider details, database aliases, and raw rejected input are not serialized. | [`tests/execution/test_public_errors.py`](../tests/execution/test_public_errors.py); schema closure and diagnostic checks in [`tests/contracts/test_schemas.py`](../tests/contracts/test_schemas.py). |

Schema applicability establishes wire shape, not authorization or semantic
privacy by itself. The exact schema/privacy boundary is described in [Draft
internal contract schemas](internal-contracts.md), and decision-level evidence
is indexed in the [Internal semantic decision index](internal-semantic-decision-index.md).

## HTTP adapter fields

| ID | Surface and emitted fields | Classification | Private or derived inputs and treatment | Focused evidence |
| --- | --- | --- | --- | --- |
| SURFACE-06 | `GET /asklens/catalog/` and `GET /asklens/capabilities/` return the complete catalog and machine-capability documents directly. | Exact internal document at an authenticated HTTP route, not an HTTP wrapper. | [`views.py`](../django_asklens/api/views.py) resolves current permissions for catalog output; capabilities remain resource-independent. Route authentication/authorization happens before handlers. | [`tests/api/test_http_characterization.py`](../tests/api/test_http_characterization.py): exact route shapes and pre-handler denials. |
| SURFACE-07 | Successful `POST /asklens/query/` query output has `question`, `response_type`, `plan`, exact `result`, `explanation`, and optional `run_id`, `presentation`, staff-only `debug`; help output has `question`, `response_type`, `routing`, exact `capabilities`, exact `catalog`, `help`, `explanation`. | HTTP adapter wrapper embedding exact documents. `question` and a caller-provided plan are Caller-supplied echo; a provider-generated plan is validated public orchestration output; `run_id` is Server-owned operational metadata. | [`querying.py`](../django_asklens/querying.py) uses only the validated public plan for normal/debug output. It does not serialize prepared state, context, permissions, scope, bindings, rows outside the exact result, or provider raw output. Presentation/routing/help cannot authorize execution. | [`tests/api/test_success_envelope_regressions.py`](../tests/api/test_success_envelope_regressions.py) proves exact result/capability/catalog embedding; [`tests/api/test_http_characterization.py`](../tests/api/test_http_characterization.py) limits staff debug to the validated plan. |
| SURFACE-08 | AskLens HTTP failures use `{error, run_id?}`; framework failures are mapped to fixed safe error children while retaining status/header semantics. | HTTP adapter wrapper around an exact error child. | [`views.py`](../django_asklens/api/views.py) intentionally discards the shared orchestration payload's question/status fields on HTTP errors. It never reflects serializer detail, unavailable member names, framework diagnostics, throttling internals, or configured database aliases. | [`tests/api/test_error_adapter_regressions.py`](../tests/api/test_error_adapter_regressions.py) and [`tests/api/test_http_characterization.py`](../tests/api/test_http_characterization.py). |
| SURFACE-09 | Run detail has `id`, `question`, `plan`, `status`, `row_count`, `duration_ms`, `error`, `created_at`. | HTTP audit wrapper: Server-owned operational metadata plus Explicit content opt-in. | [`serializers.py`](../django_asklens/api/serializers.py) blanks question by default, reduces plan to bounded safe `resource`/`intent`, and reconstructs errors only from a fixed code/message allowlist. User identity is not emitted. Full stored question/plan is returned only when `AUDIT_INCLUDE_CONTENT is True` and route/object authorization already permits access. Missing and inaccessible records share one opaque response. | [`tests/api/test_run_detail_privacy.py`](../tests/api/test_run_detail_privacy.py) covers legacy private content, safe errors, owner/reviewer authorization, opaque absence, and server-owned audit routing. |

The full route/document relationship remains recorded in the [current HTTP and
internal-envelope crosswalk](http-internal-envelope-crosswalk.md). Adapter fields
must not be inserted into the five exact schemas merely because one route emits
them.

## MCP adapter fields

| ID | Surface and emitted fields | Classification | Private or derived inputs and treatment | Focused evidence |
| --- | --- | --- | --- | --- | --- |
| SURFACE-10 | MCP discovery/validation adds `response_type`, `resource_detail`, `resource_summaries`, `rows_omitted`, `executed`, `valid`, `query_plan_schema`, guidance/explanation, or error around exact documents. MCP query execution flattens the exact result and adds `status_code` plus row-policy fields such as `mcp_row_limit`, `mcp_returned_row_count`, and `mcp_rows_truncated`. | MCP adapter wrapper. Catalog/plan/result/error children retain their exact classifications; row-policy fields are Server-owned operational metadata. | [`core.py`](../django_asklens/mcp/core.py) permission-filters full/summary discovery, revalidates plans, and omits result rows by default. Rows require host `MCP_ALLOW_ROW_RETURN=True` plus call-level `include_rows=True`, and are capped independently. Error wrappers can retain the caller-supplied question/status from shared orchestration; that is Caller-supplied echo, not a private binding/policy leak. | [`tests/mcp/test_core.py`](../tests/mcp/test_core.py) covers permission-scoped discovery, unknown-member opacity, current scope, default row omission, dual opt-in, and cap metadata. |

MCP wrappers often enter an LLM context, so their row controls are stricter than
the core result document. Omitting rows does not skip trusted execution, limits,
result counting, or audit. Changing whether MCP returns caller-supplied question
text would be an adapter API/privacy decision, not a schema correction.

## Provider and human guidance

| ID | Surface and emitted fields | Classification | Private or derived inputs and treatment | Focused evidence |
| --- | --- | --- | --- | --- | --- |
| SURFACE-11 | Planner messages contain system instructions, the caller's question, and permission-scoped catalog JSON; provider response parsing accepts strict plan plus separate presentation. Human query guidance adds summary, patterns, limitations, examples, per-resource usage flags, and coarse scope `level`/optional `kind`. | Catalog remains an Exact internal document; surrounding prose is Sanitized human guidance; the question is provider-directed caller content. | [`prompts.py`](../django_asklens/planning/prompts.py) sends no rows or samples. Catalog serialization omits bindings and permission requirements even when a protected field is visible. Scope guidance may derive a generic kind and single/multiple/all level from server-owned tokens, but never copies token strings or scope IDs. Django ORM wording is product/help prose for this Django-first package, not a model/table/binding field or backend-neutral contract claim. | [`tests/planning/test_planner.py`](../tests/planning/test_planner.py) checks model/path/permission/cardinality omission; [`tests/catalog/test_capabilities.py`](../tests/catalog/test_capabilities.py) checks sanitized scope guidance and identifier omission. |

Questions can contain sensitive caller content. Hosts choose and configure the
provider and must apply their provider/privacy policy; AskLens does not append
database rows, sample values, credentials, tenant identifiers, or private
registration metadata to the provider request.

## Audit-record detail

| ID | Surface and emitted fields | Classification | Private or derived inputs and treatment | Focused evidence |
| --- | --- | --- | --- | --- | --- |
| SURFACE-12 | Internal audit event: `timestamp`, `principal_id`, validated `resource`/`intent` when available, `status`, `row_count`, `duration_ms`, `error_code`, safe `error_message`; optional `question`/validated `plan` only under content opt-in. Built-in storage maps this to user relation, question, plan, status, row count, duration, safe error, created timestamp. | Server-owned operational metadata; question/full plan are Explicit content opt-in and are not provider or public error documents. | [`audit.py`](../django_asklens/execution/audit.py) builds one event from trusted context, emits at most once, and keeps sink/database configuration server-owned. Default database storage reduces plans to resource/intent and stores no question. Public run detail applies its own current-policy redaction even to legacy full-content rows. | [`tests/execution/test_audit_boundary.py`](../tests/execution/test_audit_boundary.py) proves metadata-only default/explicit opt-in; [`tests/api/test_run_detail_privacy.py`](../tests/api/test_run_detail_privacy.py) proves display redaction. |

A custom audit sink deliberately receives `principal_id` as server-owned
operational metadata. It is not sent to providers or serialized in catalog,
capabilities, plan, result, error, HTTP query output, MCP query output, or built-in
run detail. Host sink retention/access/redaction remains a host responsibility.

## Findings and disposition

**No confirmed private backend or policy leakage** was found in the inventoried
current outputs. Existing focused tests directly exercise private binding,
permission, tenant/scope, provider, row, diagnostic, and database-alias
sentinels. The five schemas are closed, and current exact documents omit private
properties.

The following reviewed fields are retained with explicit classifications rather
than silently removed:

| Field or behavior | Classification and disposition |
| --- | --- |
| Catalog `relation_depth` | Normalized semantic metadata used for public relationship budgets. It exposes an integer depth, not Django relation names or paths. Retain. |
| Resource `timezone`, `default_order`, enum metadata | Explicit semantic registration needed for deterministic planning/results. Retain; never infer sample values. |
| Capabilities limits, feature booleans, aggregate policies | Implementation capability/unsupported facts. Retain; `backend_restrictions` is currently empty. |
| Result `duration_ms`, row count, limit/truncation | Server-owned operational/result metadata. Retain. Authorized result `data` is intentional output, subject to adapter policy. |
| Host labels, descriptions, synonyms, enum aliases | Explicit host-authored metadata. Retain with documentation that hosts must not insert secrets or real samples. |
| Human scope `level` and `kind` | Sanitized human guidance; token values and scope IDs are omitted. Retain. |
| Human phrase “Django ORM” | Django-first product/help prose, not a private model/table/binding and not part of machine capabilities. Retain without portability claims. |
| HTTP/MCP `question` and validated public `plan` | Question and caller-provided plans are Caller-supplied echo; provider-generated plans are validated public orchestration output. Their filter values can be privacy-sensitive, but they are not server-owned backend/policy metadata. Any removal or redaction requires a separate API and privacy-policy decision. |
| HTTP/MCP `run_id`; run-detail ID/timestamps/status/count/duration | Server-owned operational metadata protected by route/object policy. Retain. |
| Full-content audit under exact boolean opt-in | Accepted Explicit content opt-in. Retain; hosts own retention, access, redaction, deletion, and provider/privacy review. |

No runtime, API shape, schema, fixture, expected output, provider behavior, or
audit policy is changed by this audit. If later evidence shows an actual private
value crossing a boundary, treat it as a security defect and add a direct
negative regression before correction. If the concern is caller-content
propagation or an already documented adapter field, stop for an explicit
privacy/API decision rather than relabeling it as backend leakage.

## Limitations

This review is source inspection plus deterministic project-controlled tests and
current CI evidence. It is not exhaustive data-flow analysis, not an external
application assessment, not a provider certification, and not an independent
security review. It does not validate whether every host-supplied label,
description, synonym, enum label/alias, question, or custom audit sink is safe.

Passing tests do not prove that an application configured correct permissions,
scope providers, route policy, provider policy, audit lifecycle, read-only
database credentials, timeouts, or MCP row settings. They do not establish a
public protocol, backend neutrality, production certification, or release
approval.
