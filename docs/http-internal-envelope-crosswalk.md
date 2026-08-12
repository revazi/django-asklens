# Current HTTP/internal-envelope crosswalk

## Status, baseline, and evidence

This is the API-2 current-state map for the optional Django REST framework
adapter. Its baseline is clean `main` at
`9f5bae15f9fe40f2be63de51022a847b064c2c43`, the squash-merged API-1 commit.
API-2 adds documentation and drift assertions only; it changes no HTTP,
execution, authorization, audit, schema, or package behavior.

The five internal documents are `catalog`, `capabilities`, `query-plan`,
`result`, and `error`. The evidence for the mapping is:

- the [API-1 HTTP characterization](../tests/api/test_http_characterization.py);
- the current [DRF views](../django_asklens/api/views.py), shared
  [querying orchestration](../django_asklens/querying.py), and
  [DRF serializers](../django_asklens/api/serializers.py);
- the contract [models](../django_asklens/contracts/_models.py), generated
  [schemas](../django_asklens/contracts/schemas/), packaged
  [accessors](../django_asklens/contracts/_access.py), and
  [schema/runtime tests](../tests/contracts/test_schemas.py);
- the [draft internal contract documentation](internal-contracts.md) and
  [language-neutral conformance documentation](conformance.md); and
- the current [result serializer](../django_asklens/results/__init__.py),
  [audit model](../django_asklens/models.py), and
  [audit-policy implementation](../django_asklens/execution/audit.py), as
  exercised by the API, execution, contract, and conformance tests.

This map uses current code and tests as implementation truth. It records where
HTTP deliberately composes internal values with adapter concerns: not every HTTP
body is an internal document, and similar field names do not establish document
identity.

## Terms

- **Internal document** — one JSON value shaped by one of the five packaged
  internal draft schemas: `catalog`, `capabilities`, `query-plan`, `result`, or
  `error`.
- **Exact document** — the complete value at that location is an instance of one
  internal document shape, with no HTTP-only members and no required internal
  members moved outside it.
- **Embedded document** — a nested value is an exact internal document, while
  its surrounding HTTP body is not.
- **HTTP adapter field** — a transport, orchestration, presentation, debug, or
  audit-reference member that is not part of the identified internal document.
- **Wrapper** — an HTTP object that embeds an internal document or spreads its
  members alongside HTTP adapter fields.
- **Transport/framework error** — an error produced by DRF parsing,
  authentication, permission, routing, or method handling rather than an
  AskLens internal `error` document.
- **Audit representation** — the policy-dependent serialization of a stored
  `SemanticQueryRun`; it is an operational record, not a query/result/error
  contract document.

Schema validation is not authorization. A schema-shaped plan, a plan shown in
help, or a previously validated plan remains untrusted and must enter the
current-request trusted execution path.

## Route and outcome matrix

| Route / outcome | Status | Body source | Internal-document relationship | Adapter fields | Audit effect | Current cleanup implication |
| --- | --- | --- | --- | --- | --- | --- |
| `GET /asklens/catalog/` success | `200` | `serialize_catalog(permissions=current_request_permissions)` | Entire body is the exact permission-scoped `catalog` document | None | No query-run audit | Preserve exact identity and the safe metadata boundary |
| `GET /asklens/capabilities/` success | `200` | `build_capabilities()` | Entire body is the exact resource-independent `capabilities` document | None | No query-run audit | Preserve exact identity and resource independence |
| `POST /asklens/query/` query success | `200` | `build_success_payload()` after `execute_plan()` | Embedded exact `query-plan`; required `result` members are spread into a larger wrapper; body is not a `result` document | `question`, `response_type`, optional `run_id`, optional `presentation`, `explanation`, optional `debug` | One configured execution audit event; a database run and `run_id` exist only when the database sink returns a run | Prefer an explicit complete `result` child in a separately authorized cleanup |
| `POST /asklens/query/` capabilities/help success | `200` | `build_capabilities_payload()` | Embedded exact `capabilities` and permission-scoped `catalog`; help wrapper is not one of the five documents | `question`, `response_type`, `capability_intent`, `routing_source`, `query_help_source`, `query_help`, optional `query_help_error`, `explanation` | No plan execution and no query-run audit | Make wrapper composition explicit without calling help a machine contract |
| `POST /asklens/query/` request-serializer rejection | `400` | `QueryView.post()` | `error` child is an exact internal `error`; outer `{response_type,error}` object is not | `response_type` | No audit | Consider one coherent safe error envelope and strict unknown request keys |
| `POST /asklens/query/` AskLens failure after request acceptance | `400` | `execute_asklens_query_request()` | `error` child is an exact internal `error`; outer `{question,status,error,run_id?}` object is not | `question`, `status`, optional `run_id` | Configured safe failure audit; rejection performs zero application-data SQL, though database mode may insert metadata | Reconcile this wrapper with request and framework failures |
| Any route, DRF/parser/auth/permission/method/not-found rejection | `400`, `403`, `404`, `405`, or `415` | DRF exception handling | `{detail: ...}` is a transport/framework error, not an internal `error` | `detail` | Transport and route-gate denials before orchestration do not audit; run-detail reads also create no new audit | Decide whether one envelope includes framework exceptions without weakening DRF gates |
| `GET /asklens/runs/<int:pk>/` success | `200` | `SemanticQueryRunSerializer` | Audit representation only; not `query-plan`, `result`, or `error` identity | All serialized audit fields | Reads an existing database audit row; creates no new query-run audit | Defer privacy, access, alias, and nonexistence policy to API-5 |
| `GET /asklens/runs/<int:pk>/` inaccessible/missing | `403` / `404` | View permission check / Django lookup and DRF handling | `{detail: ...}` transport/framework error | `detail` | No new query-run audit | API-5 must decide whether the current existence distinction remains |

The status column records current defaults and characterized outcomes, not a
future compatibility guarantee.

## `GET /asklens/catalog/`

After the configurable DRF route permission gate, the view resolves permissions
from the current server-owned request and returns
`serialize_catalog(permissions=...)` directly. The whole `200` body is therefore
an exact current `catalog` document; there is no transport wrapper around
`resources`.

The document is permission-scoped. Its safe metadata boundary includes only
visible semantic resources, fields, enum metadata, metrics, ordering, labels,
and other registered public metadata. It does not expose database rows or
sample values, Django model labels or ORM bindings/expressions, permission-token
formats, scope-provider details, QuerySets, tenant identifiers, or credentials.
The catalog establishes visible metadata, not executable authority; execution
resolves permissions and row scope again from the current request.

The route does not create a `SemanticQueryRun` audit row.

## `GET /asklens/capabilities/`

After the route permission gate, the view returns `build_capabilities()`
directly. The whole `200` body is the exact current `capabilities` document. It
contains implementation facts such as intents, type/operator support,
structural limits, feature flags, aggregate policies, and backend restrictions.

The builder takes no resource registry or request-permission input. The body is
resource-independent: it contains no catalog resources, labels, examples,
human help, scope guidance, or permission-scoped member list. Route access is
still controlled by the current DRF request. The route creates no query-run
audit.

## `POST /asklens/query/` success: query result

The request serializer accepts `question`, optional `debug`, optional
`include_presentation`, optional `plan`, and optional `presentation`. Current DRF
serializer behavior ignores unknown top-level request keys; strict unknown
request keys are a cleanup candidate, not current behavior.

On query success, shared orchestration calls `execute_plan()` with the untrusted
plan and current request. The response is a wrapper with three categories:

1. `plan` is an embedded current `query-plan` document. It is the normalized
   `QueryPlan` from the completed trusted execution, not a public prepared plan
   or reusable authorization token.
2. `columns`, `data`, `row_count`, `duration_ms`, and `result_metadata` are the
   exact core `result` fields copied from `QueryResult.to_dict()` and spread at
   the HTTP top level. Because the wrapper also has adapter members, the whole
   HTTP body is not an exact `result` document.
3. `question`, `response_type: "query"`, `explanation`, optional database
   `run_id`, optional normalized `presentation`, and optional staff-only `debug`
   are HTTP adapter fields. Presentation and debug do not alter plan semantics
   or returned values.

The internal `result` serializer adds optional `empty: true` when `data` has no
rows and omits `empty` otherwise. `build_success_payload()` currently selects
the five required result fields listed above and does not copy `empty`, even
when it was present in the core result mapping. The HTTP wrapper therefore does
not preserve that optional emitted marker. The five selected values still cover
all required fields of the current result schema, but field spreading and the
omission mean the response must not be described as identical to the core
result object.

Trusted execution emits one audit event according to server-owned policy. With
the default database metadata-only policy, the stored run has operational
resource/intent, status, row count, duration, safe error text when applicable,
and a principal reference; `question` is blank and the complete plan is not
stored. A `run_id` appears only when the configured sink returns a database
`SemanticQueryRun`. Full question and complete plan content require explicit
host opt-in.

## `POST /asklens/query/` success: capabilities and help

A help/capability question can return `200` from the same route without
executing a plan. The wrapper embeds:

- `capabilities`: an exact resource-independent internal `capabilities`
  document; and
- `catalog`: an exact current-request permission-scoped internal `catalog`
  document.

The sibling fields `question`, `response_type: "capabilities"`,
`capability_intent`, `routing_source`, `query_help_source`, `query_help`, optional
`query_help_error`, and `explanation` belong to routing and human-help
orchestration. `query_help` is a strict help model, but it is not one of the five
internal machine documents and must not be presented as one. A validated help
suggestion may contain a current-shape `plan`; that plan remains untrusted and is
revalidated with the then-current request if submitted for execution.

This outcome performs no query execution and creates no query-run audit. That
non-auditing help behavior is distinct from a data-query success.

## Errors and denials

Current HTTP failures have three non-identical forms:

1. **Request serializer parse wrapper.** Missing/blank `question` or a non-object
   JSON value handled by `QueryRequestSerializer` returns `400` as
   `{response_type: "error", error: {...}}`. The nested `error` value is an exact
   internal `error` document with `asklens.parse.invalid`; the outer object is an
   HTTP wrapper. It does not create an audit row.
2. **Accepted-plan/AskLens failure wrapper.** After request-serializer
   acceptance, an `AskLensError` from planning, plan parsing/validation, scope,
   budget, binding, compilation, execution, or provider processing returns `400`
   as `{question, status: "failed", error, run_id?}`.
   The nested safe `error` is an exact internal `error` document containing only
   code, message, and an optional bounded JSON Pointer. The outer object is not
   an ErrorDocument. Audit policy controls the failure event and optional
   database `run_id`; rejection still performs zero application-data SQL, with
   at most the allowed metadata audit insert in database mode.
3. **DRF `detail` errors.** Malformed JSON, unsupported media type,
   authentication denial, configured route-permission denial, non-staff debug
   denial, disallowed method, missing run, and inaccessible run are handled as
   DRF/framework exceptions with `{detail: ...}` and the applicable `400`, `403`,
   `404`, `405`, or `415`. These bodies are transport/framework errors, not
   internal `error` documents. The current run-detail route distinguishes an
   inaccessible existing row (`403`) from a missing row (`404`).

Thus `error` is an exact internal ErrorDocument only when it is the nested
`error` child of the first two AskLens wrappers. The wrappers themselves and
all DRF `detail` objects are not ErrorDocuments. A future coherent envelope must
not expose raw parser, serializer, provider, policy, ORM, or traceback detail,
and must preserve authentication and permission checks before execution.

## `GET /asklens/runs/<int:pk>/`

The success body is direct `SemanticQueryRunSerializer` output with `id`,
`question`, `plan`, `status`, `row_count`, `duration_ms`, `error`, and
`created_at`. It is an audit representation, not an internal `result`, `error`,
or `query-plan` document:

- `plan` is policy-dependent audit content. Under metadata-only database audit
  it is operational-only metadata such as `resource` and `intent` (or `{}` for
  an early failure); under explicit full-content opt-in it can be the complete
  validated plan.
- the AskLens audit writer stores its safe error as text, currently
  `"<code>: <message>"`, not the structured internal ErrorDocument; the run-detail
  serializer returns that model field directly.
- no result columns or result rows are stored, and the representation adds audit
  identity/timestamp fields.
- `question` and a full plan can contain sensitive content. They are blank or
  reduced by default and require explicit host full-content opt-in plus
  retention, access, redaction, and deletion policy.

Current access permits the owning authenticated user and staff. Another regular
user receives `403`; a missing primary key receives `404`. Reading detail does
not create another audit row. API-5 owns review of access, database aliases,
serialized privacy, full-content behavior, and whether nonexistence must be
opaque; this document does not choose that policy.

## Current non-identities and cleanup candidates

The crosswalk intentionally records these current non-identities rather than
forcing schema equality:

- The query-success body embeds `query-plan` but spreads `result` fields beside
  adapter fields and drops the core serializer's optional emitted `empty`
  marker.
- The capabilities/help body embeds exact `capabilities` and `catalog`
  documents, but routing and human-help fields make the wrapper a separate
  adapter shape.
- The two AskLens error wrappers differ from each other, and DRF exceptions use
  a third `{detail}` form. Only nested `error` children are exact internal
  `error` documents.
- Run detail serializes policy-dependent audit storage, not query/result/error
  documents.

Candidates for separately authorized alpha cleanup are:

1. Make `QueryRequestSerializer` reject unknown top-level keys instead of
   silently discarding them.
2. Choose one coherent safe HTTP error envelope and decide explicitly how DRF
   parser, authentication, permission, method, and not-found exception handling
   enters it. Keep route gates, opaque members, bounded pointers, and safe
   messages unchanged.
3. Make query success embed a complete result document, for example under
   `result`, rather than spreading its fields. That target naturally preserves
   optional `empty`; any alternative should explicitly justify why spreading is
   clearer and prove complete result parity.
4. Define the capabilities-help wrapper as explicit composition of exact
   `capabilities`, exact permission-scoped `catalog`, and separately named help
   and routing fields. Do not relabel human help as the internal capabilities
   document.
5. Assign run-detail privacy, full-content, access, database-alias, and
   nonexistence behavior to API-5.
6. Assign compatibility/public-export inventory and accidental export removal
   to API-3, thin-adapter/orchestration and HTTP-envelope cleanup to API-4, and
   optional-extra/import/wheel parity to API-6. None is implemented here.

The accepted alpha-breaking direction means a later authorized cleanup need not
retain accidental wire shapes or add compatibility/migration machinery. It does
not make a proposed shape stable and does not authorize API-3, API-4, API-5,
API-6, or any runtime edit.

## Recommended sequential cleanup order

The security/privacy work and coherence/ergonomics work should be reviewed
separately even when the alpha permits breaking changes.

**Must-fix security/privacy before claiming a cleaned boundary:**

1. API-5 should resolve run-detail owner/staff access, database alias behavior,
   metadata-only versus full-content exposure, and the `403`/`404` existence
   distinction. This is a policy review, not a claim that repository evidence
   has found an exploit.
2. A narrow API-4 input/error slice should enforce strict unknown request keys
   and normalize errors only with regression evidence for pre-handler auth,
   opaque member denial, safe diagnostics, current-request scope, audit privacy,
   and zero application-data SQL on rejection.

**Coherence/ergonomics after those boundaries are fixed:**

3. API-3 can remove only independently proven accidental Python/compatibility
   exports under the accepted alpha decision.
4. A following API-4 slice can embed a complete `result` child and make the
   capabilities-help composition explicit while keeping the DRF view thin and
   preserving parity with shared orchestration.
5. API-6 can finish with core/API optional-import, dependency-extra, source/wheel
   route, and artifact parity evidence.

Each item should be a small separately authorized tranche with characterization
first, narrow and full evidence, independent review, and an explicit stop at its
gate. This recommendation does not authorize any item.

## Preserved security and package boundaries

Any later cleanup must preserve all of these current invariants:

- query execution converges through `execute_asklens_query_request()` and the
  trusted `execute_plan()` facade;
- identity, permissions, catalog visibility, and row scope come from the current
  server-owned request and are re-resolved for execution;
- schema validation, preview validation, debug output, and help suggestions are
  never authorization tokens;
- rejected plans perform zero registered application-data SQL; the allowed
  database audit effect is metadata-only by default;
- every executing resource retains explicit global or fail-closed
  current-request scope, structural budgets, deterministic serialization, and
  privacy-aware audit;
- public documents and provider metadata retain private Django bindings,
  expressions, permission formats, tenant identifiers, and scope-provider
  details as private;
- DRF remains optional and absent from core-only imports;
- default audit remains metadata-only, with question/complete-plan storage only
  under explicit host opt-in; and
- execution remains read-only Django ORM execution. No LLM-generated SQL, raw
  SQL mode, mutation, or adapter bypass is introduced.

## Limitations

The five schemas remain internal, draft, unfrozen, and unversioned. This
crosswalk does not freeze the HTTP API, publish a specification, establish a
compatibility promise, prove backend neutrality, or change behavior. It is not
a public specification and not a compatibility promise.

The evidence is repository code and maintainer-operated tests at one exact
baseline. It is not external pilot/adoption evidence, not production
certification, and not an independent security audit. Passing the drift test or
a later review does not approve an API contract, authorize a release, or open
API-3 and later gates.
