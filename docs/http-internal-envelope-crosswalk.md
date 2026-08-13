# Current HTTP/internal-envelope crosswalk

## Status, baseline, and evidence

This began as the API-2 current-state map for the optional Django REST
framework adapter. Its original implementation baseline was clean `main` at
`09715e3db731803c58577c1a6bcde54c152b73de`. API-5 later replaced the run-detail/
audit boundary, API-3 cleaned the Python export surface, API-4a replaced
permissive top-level query input plus divergent AskLens-route errors, and API-4b
now replaces spread query/help success fields with explicit composition. This
remains a current implementation crosswalk rather than a stable contract.

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

API-3 removes the deprecated `django_asklens.api.querying` module and dead helper
exports. `django_asklens.querying.__all__` is exactly `AskLensQueryResponse` and
`execute_asklens_query_request`. `django_asklens.api.views.__all__` contains only
`AskLensAPIView`, `CapabilitiesView`, `CatalogView`, `QueryRunDetailView`, and
`QueryView`. Deliberate root `django_asklens` exports remain retained. Private
`_build_success_payload()` and `_build_capabilities_payload()` helpers are
implementation details, not supported imports. API-4a owns strict input and
AskLens-route errors; API-4b owns success composition. API-6 remains the next
separate packaging/import-parity PR after API-4b's post-merge gate.

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
- **Transport/framework error** — a failure produced by DRF parsing,
  authentication, permission, throttling, routing, or method handling. On the
  four AskLens views, API-4a maps it to a fixed safe internal `error` child;
  unrelated host DRF endpoints retain host-configured behavior.
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
| `POST /asklens/query/` query success | `200` | private `_build_success_payload()` after `execute_plan()` | Embedded exact `query-plan` plus a complete exact `result` child, including optional `empty` | `question`, `response_type`, optional `run_id`, optional `presentation`, `explanation`, optional `debug` | One configured execution audit event; a database run and `run_id` exist only when the database sink returns a run | Preserve exact result identity and shared-orchestrator parity |
| `POST /asklens/query/` capabilities/help success | `200` | private `_build_capabilities_payload()` | Embedded exact `capabilities` and permission-scoped `catalog`; `routing` and human `help` are explicit adapter objects, not internal documents | `question`, `response_type`, `routing`, `help`, `explanation` | No plan execution and no query-run audit | Keep machine documents distinct from human guidance |
| `POST /asklens/query/` request-serializer rejection | `400` | strict `QueryRequestSerializer` plus `QueryView.post()` | Exact internal `error` child under the sole `{error}` envelope | None | No audit and no application-data SQL | Unknown keys and malformed request shape reject without reflected diagnostics |
| `POST /asklens/query/` AskLens failure after request acceptance | `400` | `execute_asklens_query_request()` adapted by `QueryView.post()` | Exact existing internal `error` child under `{error,run_id?}` | Optional database audit `run_id` only | Configured safe failure audit; rejection performs zero application-data SQL, though database mode may insert metadata | Preserve shared orchestration/audit while removing question/status wrapper fields |
| Any AskLens route, parser/media/auth/permission/debug/method/throttle/not-found/unexpected rejection | Existing `4xx`/`5xx` status | route-local `AskLensAPIView.handle_exception()` | Fixed exact internal `error` child under `{error}` | None | Transport/route/strict-input denials remain unaudited; run-detail reads create no audit | Preserve applicable `Allow`, `WWW-Authenticate`, and `Retry-After`; non-AskLens host views are unchanged |
| `GET /asklens/runs/<int:pk>/` success | `200` | Authorization-filtered selected-alias lookup plus `SemanticQueryRunSerializer` | Audit representation only; not `query-plan`, `result`, or `error` identity | All serialized audit fields; `error` is safe structured audit metadata, not stored text or schema identity | Reads an existing database audit row; creates no new query-run audit | API-5 deliberately hardens access, content display, error output, and routing without claiming schema identity |
| `GET /asklens/runs/<int:pk>/` inaccessible/missing | `404` / `404` | One authorization-filtered lookup and route-local adapter | Same fixed `{error: {code: "asklens.member.unavailable", ...}}` envelope | None | No new query-run audit | Preserve existence opacity; configured route gates still run first |
| `GET /asklens/runs/<int:pk>/` invalid/unavailable audit alias | `503` | Fixed route-local adapter response | Exact fixed `asklens.execute.failed` child under `{error}` | None | No fallback read and no audit side effect | Do not reflect alias/database diagnostics or fall back to `default` |

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

The strict request serializer accepts only `question`, optional `debug`, optional
`include_presentation`, optional `plan`, and optional `presentation`. Every other
top-level key—including user, permission, tenant, scope, and audit-routing
claims—is rejected before shared orchestration, audit, or application-data SQL.
Neither the unknown name/value nor serializer diagnostics are reflected.

On query success, shared orchestration calls `execute_plan()` with the untrusted
plan and current request. The response is a wrapper with three categories:

1. `plan` is an embedded current `query-plan` document. It is the normalized
   `QueryPlan` from the completed trusted execution, not a public prepared plan
   or reusable authorization token.
2. `result` is the complete `QueryResult.to_dict()` mapping and therefore an
   exact current internal result document. It contains `columns`, `data`,
   `row_count`, `duration_ms`, and `result_metadata`, and preserves optional
   `empty: true` when no rows are emitted.
3. `question`, `response_type: "query"`, `explanation`, optional database
   `run_id`, optional normalized `presentation`, and optional staff-only `debug`
   are HTTP adapter fields. Presentation and debug do not alter plan semantics
   or returned values.

Result members are no longer duplicated or spread at the HTTP top level. The
shared framework-neutral orchestrator owns this composition; `QueryView` still
returns its payload directly on success. Admin and the packaged frontend consume
the nested result. MCP consumes the same shared result and deliberately adapts
it back into its existing row-policy response so default row omission and the
separate MCP return cap remain intact.

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

The sibling adapter objects are now explicit:

- `routing` contains the strict capability-intent value under `intent` and the
  routing source under `source`; and
- `help` contains `source`, strict human guidance under `content`, and optional
  safe provider-fallback text under `error`.

`help.content` is a strict help model, but neither `routing` nor `help` is one of
the five internal machine documents. A validated help suggestion may contain a
current-shape `plan`; that plan remains untrusted and is revalidated with the
then-current request if submitted for execution.

This outcome performs no query execution and creates no query-run audit. That
non-auditing help behavior is distinct from a data-query success.

## Errors and denials

Every handled failure emitted by the four views inheriting `AskLensAPIView` now
uses exactly one HTTP adapter shape:

```json
{
  "error": {
    "code": "asklens.parse.invalid",
    "message": "The AskLens request could not be parsed.",
    "pointer": "/optional-safe-pointer"
  },
  "run_id": 123
}
```

`pointer` remains optional inside the exact internal ErrorDocument. Top-level
`run_id` is present only when an accepted AskLens planning/execution failure
created a database audit row. Request-shape, unknown-key, parser/media,
authentication/permission/debug, method, throttle, not-found, audit-unavailable,
and unexpected failures have no run id. No failure body contains
`response_type`, an echoed `question`, redundant `status`, or DRF `detail`.

The route-local fixed mappings are:

- request/JSON parser/media/content negotiation/method failures →
  `asklens.parse.invalid`, “The AskLens request could not be parsed.”;
- authentication/configured permission/Django or DRF permission/debug denials →
  `asklens.authorization.denied`, “The current request is not authorized.”;
- opaque missing/inaccessible run lookup → `asklens.member.unavailable` with
  the existing opaque member message;
- throttling → `asklens.budget.exceeded`, “The AskLens request exceeds an
  execution limit.”; and
- unavailable audit records, unclassified framework exceptions, and unexpected
  route-local exceptions → `asklens.execute.failed`, “The AskLens request could
  not be completed.”

Accepted AskLens planning, parse/validation, authorization, scope, budget,
binding, compilation, execution, and provider failures retain their existing
exact `error` child, including a bounded safe pointer, while `QueryView` removes
the shared Python orchestrator's question/status wrapper only at the HTTP
boundary. Their configured privacy-aware failure audit and optional database
`run_id` are unchanged. Rejections continue to perform zero application-data
SQL, with at most the allowed metadata audit insert after orchestration has
accepted the request.

The adapter calls DRF's normal exception handling first for handled framework
exceptions, so HTTP statuses plus applicable `Allow`, `WWW-Authenticate`, and
`Retry-After` headers remain intact. Authentication, permission, and throttle
ordering remains DRF-owned and precedes handlers. The override exists only on
`AskLensAPIView`; unrelated host DRF endpoints retain host-configured exception
bodies, and there is no global exception-handler setting.

## `GET /asklens/runs/<int:pk>/`

The success body is direct `SemanticQueryRunSerializer` output with `id`,
`question`, `plan`, `status`, `row_count`, `duration_ms`, `error`, and
`created_at`. It is an audit representation, not an internal `result`, `error`,
or `query-plan` document:

- Current `AUDIT_INCLUDE_CONTENT` policy is enforced at display time, not merely
  ingestion. Unless the setting is exactly boolean `True`, `question` is blank
  and `plan` is reduced to allowlisted, conservatively shaped `resource` and
  `intent` operational metadata, even for a legacy/manually populated row with
  fuller stored content. Explicit boolean `True` permits an authorized viewer
  to receive the stored question and full plan.
- The model still stores AskLens writer errors as text, but the serializer never
  returns that free-form field. A failed row with a recognized stored AskLens
  code receives canonical safe `{code, message}` metadata; unknown or malformed
  text receives one fixed generic safe error. Success and blank errors are
  `null`. This is an audit representation and is not an exact internal error
  document merely because its safe fields have similar names.
- no result columns or result rows are stored, and the representation adds audit
  identity/timestamp fields.
- explicit full-content retention makes access, redaction, deletion, backup,
  replica, and alternate display/export policy the host's responsibility. Hosts
  must not write private Django bindings, permission strings, tenant IDs,
  credentials, rows, provider payloads, raw rejected content, or database
  diagnostics into public audit surfaces.

Configured route-level permission classes still execute first. Run lookup then
uses an authorization-filtered queryset: the authenticated owner may read the
row, while cross-user review requires Django's global
`asklens.view_semanticqueryrun` permission. `is_staff` alone is insufficient;
active superusers follow normal `has_perm()` behavior. Missing and inaccessible
IDs receive the same fixed opaque `404` `asklens.member.unavailable` envelope,
and reading run detail creates no audit row.

`AUDIT_DATABASE_ALIAS=None` preserves ordinary Django read routing. A configured
non-empty server-owned alias is applied explicitly to both built-in database
audit writes and run-detail reads; no client field selects it and there is no
fallback to `default`. Malformed, nonexistent, unavailable, or missing-table
configuration uses normal sink-failure behavior for writes and a fixed safe
`503` `asklens.execute.failed` envelope for reads without reflected diagnostics.
Explicit lifecycle-command
`--database` selection remains independent.

## Current non-identities and cleanup candidates

The crosswalk intentionally records exact identities and remaining non-
identities without forcing the complete HTTP wrapper into one schema:

- Query success embeds exact `query-plan` and complete exact `result` children;
  the surrounding HTTP body remains an adapter wrapper.
- The capabilities/help body embeds exact `capabilities` and `catalog`
  documents. Explicit `routing` and `help` objects remain adapter shapes, and
  `help.content` is not relabeled as a machine document.
- AskLens-route errors now share one `{error, run_id?}` adapter shape. The nested
  `error` is an exact internal ErrorDocument; optional top-level `run_id` is an
  HTTP audit reference rather than part of that document.
- Run detail serializes a policy-dependent audit representation, not query/
  result/error schema identity. API-5 now makes that representation safe at the
  current access, content, stored-error, and database-routing boundary.

API-4a is no longer a remaining candidate: `QueryRequestSerializer` rejects
unknown top-level keys, and only the four AskLens DRF views normalize serializer,
parser/media, authentication, permission/debug, method, throttle, opaque lookup,
audit-unavailable, accepted AskLens, and unexpected errors. Required headers,
route ordering, audit effects, member opacity, and zero application-data SQL are
preserved.

API-4b is no longer a remaining candidate: it embeds the complete result,
preserves `empty`, and explicitly separates machine documents from routing and
human help. API-3 previously removed the deprecated Python compatibility module
and accidental helper exports while retaining the two canonical querying
exports, five view-class exports, and deliberate root exports. API-4a completed
strict-input/error cleanup.

The accepted alpha-breaking direction permits these replacements without
compatibility/deprecation or consumer migration machinery. It does not make the
current shape stable. API-6 is authorized only as the next separate PR after
API-4b merge, cleanup, and passing post-merge CI; it is not part of API-4b.

## Recommended sequential cleanup order

The security/privacy work and coherence/ergonomics work should be reviewed
separately even when the alpha permits breaking changes.

**Completed boundary work reflected in this current map:**

1. API-5 resolves run-detail owner/explicit-permission access, selected database
   alias behavior, metadata-only versus full-content display, stored free-form
   errors, and the former `403`/`404` existence distinction. This is a deliberate
   alpha security/privacy hardening change, not an exploit claim or a declaration
   that the audit representation is a stable schema.
2. API-3 removes only the independently evidenced accidental Python/
   compatibility exports under the accepted alpha decision.
3. API-4a enforces strict unknown query keys and one safe route-local error
   envelope while preserving statuses, headers, gates, opacity, audit, and
   application-data SQL boundaries.
4. API-4b embeds a complete `result` child and makes capabilities/help
   composition explicit while keeping the DRF view thin and preserving parity
   with shared orchestration.

**Next separately gated workflow:**

5. API-6 is authorized to finish core/API optional-import, dependency-extra,
   source/wheel route, and artifact parity evidence only after API-4b merge,
   cleanup, and green post-merge CI.

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
- default audit remains metadata-only, with question/complete-plan storage and
  display only under explicit host opt-in;
- run detail remains behind configured route gates plus owner/global audit-view
  authorization, opaque lookup, safe structured stored-error output, and one
  optional server-owned audit alias with no client input or broad fallback; and
- execution remains read-only Django ORM execution. No LLM-generated SQL, raw
  SQL mode, mutation, or adapter bypass is introduced.

## Limitations

The five schemas remain internal, draft, unfrozen, and unversioned. This
crosswalk does not freeze the HTTP API, publish a specification, establish a
compatibility promise, or prove backend neutrality. API-4b changes only success
composition; it does not extend API-5 audit access or API-4a request/error
behavior. This is not a public specification and not a compatibility promise.

The evidence is repository code and maintainer-operated tests over the bounded
API-2/API-3/API-4a/API-4b/API-5 changes. It is not external pilot/adoption
evidence or production certification, and it is not an independent security audit. Passing
the drift test or a later review does not make run detail schema-identical to an
internal document, approve an API contract, authorize a release, or start
API-6 before the explicit API-4b post-merge gate.
