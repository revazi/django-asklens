# Alpha surface inventory for stable-release decisions

## Status

This document inventories the current unreleased Django AskLens alpha surface so
roadmap issue #66 can later select an intentionally narrow stable contract. It
records exposure and evidence; it does not accept compatibility commitments.
**No surface is accepted as stable** by this inventory.

The inventory describes the source tree that first added it, based on `main` at
`8841b490c46d2be03ee17434fd7ab8a058254ee7`. Recheck source, installed artifacts,
and tests against any later release candidate. PyPI `0.1.0a1`, unreleased
`main`, and a maintainer-supplied exact candidate remain different artifact
contexts under the [support lifecycle](support-lifecycle.md).

## Classification rules

| Classification | Meaning in this inventory |
| --- | --- |
| **Stable** | None accepted. Only an explicit #66 decision can put a named surface here. |
| **Provisional** | Deliberately exposed or documented current alpha behavior. It may still change through a separately authorized, tested alpha change. |
| **Optional** | Exposed only when an extra, adapter, or reference surface is selected. Optional does not mean stable. |
| **Internal** | Package implementation or evidence surface, not a supported caller contract even when Python can technically import it. |
| **Unsupported** | Deliberately excluded behavior or claim. |

`__all__`, documentation, schema packaging, source/wheel parity, and passing
tests are evidence of current exposure. None independently accepts SemVer scope,
a deprecation window, wire compatibility, or a stable support lifetime.

## Python surfaces

### Deliberate top-level and core imports

The package currently has **10 deliberate root exports**:

```text
CONTRACT_SCHEMA_NAMES
Metric
SemanticResource
__version__
build_capabilities
get_contract_schema
get_resource
list_contract_schemas
register
serialize_catalog
```

They are provisional alpha imports. The contract-schema accessors are public
Python accessors to internal documents; exposing an accessor does not make the
returned schema stable or public specification material.

Other current import families are:

| Import family | Exact current exposure | Classification and boundary |
| --- | --- | --- |
| `django_asklens.catalog` | `CatalogRegistry`, `FieldSpec`, `Metric`, `SemanticResource`, `default_registry`, `register`, `get_resource`, `serialize_catalog`, `build_capabilities` | Provisional registration/catalog surface. Public semantic keys remain separate from private Django bindings. |
| `django_asklens.execution` | `QueryResult`, `execute_plan`, `run_query_plan` | Provisional trusted execution surface. `execute_plan` is mandatory for execution. `run_query_plan` is deprecated and is not a stable-surface candidate. |
| `django_asklens.querying` | `AskLensQueryResponse`, `execute_asklens_query_request` | Provisional shared question/help orchestration. Current response composition is explicitly alpha. |
| `django_asklens.exceptions` | `PublicAskLensError`, `public_error_payload`, current namespaced error behavior | Provisional documented failure surface. Internal diagnostic exception classes and causes are not a caller compatibility promise. |
| `django_asklens.access` | `IsAuthenticated`, `can_access_asklens`, and permission-gate resolution helpers | Provisional access helpers. Hosts still own authentication and principal construction. |
| `django_asklens.permissions` | `RequestPermissionsGetter`, `default_request_permissions`, `get_request_permissions`, `resolve_request_permissions_getter` | Provisional host-integration helpers. Permission values remain server-owned. |
| `django_asklens.contracts` | `CONTRACT_SCHEMA_NAMES`, `ContractSchemaName`, `get_contract_schema`, `list_contract_schemas` | Provisional accessors over internal, unfrozen documents. |
| `django_asklens.compiler.ResultColumn` | Importable compiler/result helper | Internal for stable-surface decisions. Compilation and prepared/bound state are not public execution APIs. |

### Broad planning and result helper exposure

`django_asklens.planning` currently exports constants, Pydantic plan/provider
models, parsing, validation, and planning helpers. The current names include:

```text
SUPPORTED_DATE_TRUNCS
SUPPORTED_FILTER_OPERATORS
SUPPORTED_INTENTS
SUPPORTED_ORDER_DIRECTIONS
SUPPORTED_PRESENTATION_KINDS
AskLensProviderResponse
AskLensProviderResult
FilterSpec
GroupBySpec
MetricSpec
OrderBySpec
PlanLimits
PlannerProviderResponse
PlannerRequest
PlannerResult
PresentationSpec
QueryPlan
build_planner_request
get_asklens_provider_response_json_schema
get_query_plan_json_schema
parse_and_validate_query_plan
parse_asklens_provider_response
parse_planner_provider_response
parse_presentation
parse_query_plan
plan_asklens_response
plan_question
validate_query_plan
```

`django_asklens.results` currently exports:

```text
SUPPORTED_PRESENTATION_KINDS
NormalizedPresentation
SerializedColumn
SerializedResult
SerializedRowsPayload
normalize_presentation
serialize_query_result
serialize_rows
```

These are provisional alpha helper/model surfaces, not one accepted stable unit.
Structural parsing and preview validation never authorize execution. #66 must
select names individually if any become stable rather than freezing every
currently importable helper.

### Provider imports

`django_asklens.llms` exposes `DummyProvider`, `LLMMessage`, `LLMProvider`,
`OpenAICompatibleProvider`, and `get_llm_provider`. They are provisional provider
integration surfaces. The dummy provider remains the default; live-provider
quality, credentials, network behavior, and service terms are not package
compatibility guarantees.

## Settings

Source currently defines **37 current `DJANGO_ASKLENS` keys**. They are grouped
below to make a later decision explicit rather than accidentally stabilizing the
whole settings mapping.

| Family | Current keys | Classification |
| --- | --- | --- |
| Scope and structural budgets | `DEFAULT_SCOPE_MODE`, `MAX_ROWS`, `DEFAULT_LIMIT`, `MAX_PLAN_BYTES`, `MAX_FILTERS`, `MAX_SELECTED_FIELDS`, `MAX_ORDER_BY`, `MAX_JOINS`, `MAX_RELATIONSHIP_EDGES`, `MAX_IN_VALUES`, `MAX_FILTER_VALUES`, `MAX_METRICS`, `MAX_GROUP_BY` | Provisional core/security configuration. Enforcement is mandatory even though exact defaults are implementation settings. |
| Access and request permissions | `API_PERMISSION_CLASSES`, `REQUEST_PERMISSIONS_GETTER` | Provisional host integration; trusted values stay server-owned. |
| Audit | `AUDIT_MODE`, `AUDIT_SINK`, `AUDIT_INCLUDE_CONTENT`, `AUDIT_DATABASE_ALIAS` | Provisional security/operations configuration. Metadata-only remains the default. |
| Provider/planning | `LLM_BACKEND`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS`, `LLM_TEMPERATURE`, `LOG_LLM_IO`, `PROMPT_RESOURCE_SHORTLIST_LIMIT`, `DUMMY_PLANS`, `DUMMY_DEFAULT_PLAN` | Provisional provider configuration; secrets and live behavior remain host-owned. |
| Hard-off safety flags | `ALLOW_RAW_SQL`, `SEND_SAMPLE_ROWS_TO_LLM` | Provisional configuration names whose only supported safe behavior is false; they do not reserve future unsafe modes. |
| Frontend | `FRONTEND_PERMISSION_CHECK`, `FRONTEND_TITLE`, `FRONTEND_SUBTITLE`, `FRONTEND_STARTER_QUESTIONS` | Optional reference-frontend configuration. |
| MCP | `MCP_ALLOW_ROW_RETURN`, `MCP_MAX_RETURNED_ROWS` | Optional adapter configuration; row return stays host-and-request gated. |

Unknown settings behavior, default-value compatibility, import-string handling,
and per-key deprecation rules remain #66/#67 decisions. This inventory changes
none of them.

## Commands and database-owned surface

Current operator commands are:

- `check_asklens` — prints aggregate process-local registry counts and optionally
  fails on an empty registry with `--fail-on-empty`; it does not query application
  data or invoke scope providers.
- `redact_asklens_audit` — preview by default; explicit `--execute` redacts
  eligible built-in audit content in bounded batches.
- `purge_asklens_audit` — preview by default; explicit `--execute` irreversibly
  deletes eligible built-in audit rows with documented Django collector/signal
  effects and partial-progress limits.

They are provisional alpha operational commands with installed-core-wheel,
SQLite, and representative PostgreSQL evidence. Their names, flags, output,
exit behavior, and lifecycle guarantees are not accepted stable by this map.
Custom sinks, backups, replicas, legal retention, scheduling, external signal
effects, and complete user/tenant workflows remain host-owned.

The package owns `SemanticQueryRun`, the `AskLensQuery` admin proxy, and
migrations `0001_initial` and `0002_add_admin_query_proxy`. Their current
installation and forward migration are evidenced, but #66 must define supported
upgrade origins, migration compatibility, and rollback/data guarantees. The
packaged audit admin is an optional view-only operations surface, not a universal
host authorization or storage boundary.

## Optional HTTP surface

Installing the `api` extra exposes five view classes—`AskLensAPIView`,
`CatalogView`, `CapabilitiesView`, `QueryView`, and `QueryRunDetailView`—and four
routes:

| Route | Current relationship | Classification |
| --- | --- | --- |
| `GET /asklens/catalog/` | Exact current permission-scoped catalog document | Optional alpha adapter surface |
| `GET /asklens/capabilities/` | Exact current machine-capabilities document | Optional alpha adapter surface |
| `POST /asklens/query/` | Shared orchestration wrapper containing exact current plan/result or catalog/capabilities/error children where applicable | Optional alpha adapter surface |
| `GET /asklens/runs/<int:pk>/` | Policy-filtered audit representation, not a query/result/error document | Optional alpha operations surface |

Current statuses, headers, strict request keys, error envelopes, member/run
opacity, audit effects, and source/wheel parity are characterized in the
[HTTP/internal-envelope crosswalk](http-internal-envelope-crosswalk.md). That
current evidence does not accept route, method, status, envelope, serializer, or
view-class compatibility for a stable release.

DRF remains absent from core imports. Optional installation must not weaken the
trusted execution facade, current request authorization/scope, structural
budgets, audit privacy, or zero-application-data-SQL rejection.

## Optional MCP surface

`django_asklens.mcp` currently exposes:

```text
DEFAULT_MCP_PLAN_QUESTION
MCP_ROW_RETURN_POLICY
AskLensMCPToolSet
RequestFactory
apply_mcp_row_policy
asklens_capabilities
asklens_describe_resource
asklens_execute_plan
asklens_query
asklens_query_plan_schema
asklens_validate_plan
create_fastmcp_server
mcp_max_returned_rows
mcp_row_return_allowed
```

These are optional alpha surfaces. The framework-neutral helpers/wrapper and the
FastMCP bridge may receive different stability decisions; importability from one
module does not require one compatibility tier. `asklens_execute_plan` and
`asklens_query` converge on trusted execution. Validation is not authorization,
client policy selectors remain excluded, and rows remain omitted unless both
host policy and the tool request allow them.

The MCP extra and current source/wheel checks are evidence of optional packaging
and behavior, not production authentication, transport security, independent
client compatibility, or a stable wire protocol.

## Serialized documents

The package contains five current JSON documents and Draft 2020-12 schemas:

- `catalog`
- `query-plan`
- `capabilities`
- `result`
- `error`

They remain **internal, draft, unfrozen, and unversioned**. Current schema,
language-neutral fixture, SQLite, PostgreSQL, HTTP-crosswalk, and leakage-audit
evidence does not turn them into a public specification or compatibility
promise. A schema-valid plan remains untrusted and must enter `execute_plan()`.

HTTP and MCP wrappers are not automatically identical to these documents. Run
detail is an audit representation. Help, routing, presentation, row-omission,
and audit-reference members remain adapter concerns. Issue #66 must choose
whether any exact document becomes stable, remains internal, or needs explicit
version/extension policy first.

## Internal and unsupported surfaces

Internal surfaces include:

- prepared/bound execution state and execution-context identity/revision;
- compiler functions, ORM aliases, Django bindings, expressions, QuerySets,
  model labels, scope providers, and diagnostic causes;
- private orchestration, adapter, audit, schema-generation, and serialization
  helpers whose names begin with `_` or are not selected by #66;
- conformance harness setup, trusted clocks, synthetic scenario mappings, and
  test-project implementation details; and
- local `.agents` planning/evidence files.

Unsupported behavior and claims include:

- LLM-generated or caller-supplied raw SQL;
- mutations, arbitrary joins/expressions, cross-resource plans, and automatic
  model/field exposure;
- client-controlled identity, permissions, tenant IDs, scope, clock, audit
  routing, or prepared state;
- treating preview validation as an execution token;
- backend-neutral, NDC, Drizzle, generated-SDK, public-specification,
  production-certification, or independent-security-review claims; and
- treating SQLite or representative PostgreSQL tuples as every-database or
  Cartesian production evidence.

## Decision boundary

This inventory makes no stable-surface, SemVer, deprecation, removal, upgrade,
rollback, data-migration, document-version, release, or support-exception
decision. Roadmap **issue #66** must explicitly select:

- the first stable version;
- exact stable imports, settings, commands, routes/envelopes, adapters, and
  documents;
- ordinary deprecation/removal windows and immediate security-break treatment;
- supported fresh-install/upgrade/migration/rollback expectations;
- required, recommended, and optional release gates; and
- host-owned responsibilities and residual risks.

Until that acceptance, every current caller-facing item above remains
provisional or optional alpha exposure. Stable remains an empty classification.
R5/R6, release, Drizzle, and public-specification gates are unchanged.

## Existing evidence to reuse

Later decisions should reuse rather than duplicate:

- `tests/test_export_surface.py` for deliberate root/querying/view exports;
- `tests/test_import_boundaries.py` and `tests/test_api6_package_evidence.py` for
  optional dependency and source/wheel isolation;
- API characterization and the HTTP/internal-envelope crosswalk for routes;
- MCP core/example/omission tests for helper and row-policy behavior;
- contract-schema, conformance, semantic-index, and leakage-audit evidence for
  serialized documents; and
- lifecycle-command, migration, build/Twine, installed-wheel, PostgreSQL, and
  reference-smoke evidence for current artifacts.

A future stable-contract test should be added only after #66 accepts the exact
surface. This inventory guard checks the map and its explicit empty-stable
boundary; it is not a duplicate contract suite.
