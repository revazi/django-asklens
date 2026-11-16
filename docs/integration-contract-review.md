# Integration contract review — issues #191 and #183

## Evidence and decision scope

This review uses source baseline
`1188e981b5fb4fba468f7ecfcf97e0886aa22874` (merged
[#190](https://github.com/revazi/django-asklens/issues/190)), the normal installed
consumer delivered in [#184](https://github.com/revazi/django-asklens/issues/184),
and the installed API/admin/MCP recipes in
[#186](https://github.com/revazi/django-asklens/issues/186).
The [typing inventory](typing.md) supplies the exact import list; this review
adds observed dependencies, decisions and change costs, not another API list.
The [compatibility policy](compatibility.md) remains authoritative.

**Observed** below means checked-in example/consumer code with repository or
maintainer-operated installed-artifact evidence. It does not mean independent
adoption. No consenting external integration findings or executed TypeScript
consumer findings were supplied to this review. Possible future consumers are
labelled **prospective**, not inferred from downloads, importability, or issue
interest. All existing consumer fixtures are synthetic. Public `0.3.2` wheel
verification in #184 is distinct from same-version candidate-wheel verification
and newer source-only example files in #186/#190.

## Observed integration inventory

Links name the implementation and executable consumer evidence, not new
compatibility guarantees. Settings are keys of `DJANGO_ASKLENS` unless noted.

| Consumer and observed dependency | Evidence | Decision and compatibility cost |
| --- | --- | --- |
| Core quickstart imports root `register`; declares private bindings, timezone, resource permission, `context_scoped` scope callback and deterministic order. `ShopConfig.ready()` imports registration once. Identity comes from a real server-created request, not the plan. | [registration](../examples/quickstart/shop/asklens_registration.py), [startup](../examples/quickstart/shop/apps.py), [CLI](../examples/quickstart/shop/management/commands/ask_orders.py), [consumer regressions](../examples/quickstart/shop/tests.py) | **Retain governed documented registration calls.** Renaming semantic keys such as `product` would invalidate the host's dummy plans and UI; changing a private binding without changing the semantic key need not. Do not freeze undocumented dataclass construction or scope callback internals. |
| The core tutorial and installed typing consumer import root/catalog `Metric`, `SemanticResource`, `register`, `get_resource`; catalog-only `CatalogRegistry`, `default_registry`; execution `execute_plan`, `QueryResult`; exceptions `PublicAskLensError`, `public_error_payload`; observability `ObservabilityEvent`. | [core tutorial](quickstart-core.md), [positive consumer](../tests/installed_consumer/typing/positive.py), [negative consumer](../tests/installed_consumer/typing/negative.py), [export tests](../tests/test_export_surface.py), [compatibility tests](../tests/test_compatibility_contract.py) | **Retain the exact governed subset.** Root does not export the registry names or event type. Keep documented result access, ten public error categories and eight event fields; static coverage is bounded, not an ORM/request/draft-envelope typing promise. |
| CLI uses provisional `execute_asklens_query_request`, `AskLensQueryResponse.response_type` and nested `payload["result"]`/`payload["error"]`. It prints a deliberately smaller envelope than HTTP and exits nonzero for error/non-query outcomes. | [CLI](../examples/quickstart/shop/management/commands/ask_orders.py), [question orchestrator](../django_asklens/querying.py), [installed tutorial runner](../.github/scripts/quickstart_smoke.py) | **Retain as provisional**, not a governed alternative to `execute_plan`. Removing the two deliberate querying exports or changing nesting requires a CLI/adapter recipe update. Execution still converges on the facade. |
| Base example explicitly selects `LLM_BACKEND="dummy"`, exact `DUMMY_PLANS`, `DUMMY_DEFAULT_PLAN=None`, `AUDIT_MODE="database"`, `AUDIT_INCLUDE_CONTENT=False`. No provider key or live endpoint is needed. | [settings](../examples/quickstart/quickstart/settings.py), [dummy provider tests](../tests/llms/), [provider guidance](providers.md) | **Retain as provisional configuration.** Changing exact-match/default behavior breaks the first-run task; update its plans, docs and regression expectations together. Do not reinterpret arbitrary wording or add a permissive fallback. |
| Web/API recipe imports `django_asklens.api.urls` and configures `API_PERMISSION_CLASSES`, `REQUEST_PERMISSIONS_GETTER=None`; Django session/auth/CSRF wiring belongs to the host. Native admin is core-only; API-backed UI needs the `api` extra. | [web settings](../examples/quickstart/quickstart/web_settings.py), [API settings/routes](../examples/quickstart/quickstart/api_settings.py), [API recipe](../examples/quickstart/shop/api_recipe.py), [admin recipe](../examples/quickstart/shop/admin_recipe.py) | **Retain optional/provisional adapters.** Session/CSRF, current-request permission resolution and scope are required security invariants, not permission to freeze all routes, view classes or settings. Transport changes cost host routing/authentication and recipe retesting. |
| HTTP uses catalog/capabilities GETs; query POST takes `question`, optional `debug`, `include_presentation`, `plan`, `presentation`, rejects unknown top-level keys; query success nests `plan` and complete `result`, help nests `catalog`/`capabilities` plus adapter `routing`/`help`; errors nest `error` with optional database `run_id`. Run detail is an authorization-filtered audit representation. | [serializers](../django_asklens/api/serializers.py), [views](../django_asklens/api/views.py), [HTTP characterization](../tests/api/test_http_characterization.py), [full envelope crosswalk](http-internal-envelope-crosswalk.md) | **Retain current composition as provisional.** For example, spreading `result.data` to the top level would break shipped UI code. HTTP status/headers/wrappers are not governed core document contracts; preserve safe errors and existence opacity regardless of shape changes. |
| Custom table reads `response_type`, `result.columns`, `result.data`, `row_count`, `result_metadata.truncated`, and safe `error.code`. It uses declared columns/text rendering, same-origin session/CSRF and clears stale results. Native admin and packaged frontend also consume nested results. | [table script](../examples/quickstart/shop/static/shop/table.js), [custom UI](custom-ui.md), [browser consumer](../tests/e2e/quickstart_table.py), [admin/frontend templates](../django_asklens/templates/) | **Retain the reference consumers, not a UI product contract.** A column/envelope change costs DOM, empty/error/limited-state and accessibility-basic retesting. No chart-builder, pagination cursor or full accessibility certification is implied. |
| MCP imports `AskLensMCPToolSet`, `create_fastmcp_server`, provisional `can_access_asklens`; refetches active identity from host context each call. Recipe disables the question tool, defaults to row omission, uses `MCP_ALLOW_ROW_RETURN` and `MCP_MAX_RETURNED_ROWS`. It previews a plan then executes it with current identity. | [host MCP wiring](../examples/quickstart/quickstart/mcp.py), [MCP settings](../examples/quickstart/quickstart/mcp_settings.py), [recipe](../examples/quickstart/shop/mcp_recipe.py), [MCP guide](mcp-integration.md) | **Retain optional/provisional helpers and row policy.** MCP adapts shared results to its own `data`, `rows_omitted`, `row_return_denied`, `mcp_returned_row_count`, `mcp_row_limit`, `mcp_rows_truncated` metadata; it is not the HTTP envelope. Host AND invocation row consent and return cap remain mandatory. Helper/schema checks do not prove production transport authentication. |
| Provider orchestration uses reviewed dummy envelopes; OpenAI-compatible source/candidate mocks exercise copied strict wire schemas and normalization before ordinary validation. Custom providers, planning models, prompts, presentation and settings remain provisional. | [provider policy and remaining #188 gates](providers.md#offline-strict-schema-gate-resolved-live-acceptance-still-incomplete), [provider tests](../tests/llms/), [planning tests](../tests/planning/) | **Retain current boundary adaptation; defer live acceptance to #188.** Wire omission markers are not application null/default semantics, document versions or changes to dummy/custom providers. No live-provider use, arbitrary-NL success or lifecycle acceptance is observed here. |
| Complex demo/operational fixtures exercise budget, access, frontend, audit routing and observability configuration beyond the minimal consumer. These are repository-owned scenarios, not external host evidence. | [test-project settings](../tests/test_project/settings.py), [settings defaults](../django_asklens/settings.py), [host controls](host-throttle-and-audit-controls.md), [observability tests](../tests/execution/test_observability.py) | **Retain existing classifications.** Only `OBSERVABILITY_SINK`'s documented callback/default-off behavior is governed; other settings/default resolution remain provisional. Recheck every enabled limit/access/audit configuration on upgrade; do not turn the whole defaults mapping into a compatibility promise. |

### Persisted and reusable documents actually present

The package's database persistence is the operational
[`SemanticQueryRun`](../django_asklens/models.py) audit row, not a saved-query
product or reusable authorization object. The model stores principal reference,
question text, JSON `plan`, status, row count, duration, error text and timestamp.
The [audit writer](../django_asklens/execution/audit.py) defaults to blank
question and bounded resource/intent metadata in `plan`, **not a complete
query-plan document**. Explicit `AUDIT_INCLUDE_CONTENT=True` can retain full
question/validated-plan content; it is not enabled for onboarding. The
[run serializer](../django_asklens/api/serializers.py) applies current content
policy and safe error mapping on reads; raw stored error text is not a public
error document. [Audit boundary tests](../tests/execution/test_audit_boundary.py)
and the installed recipes verify metadata-only behavior.

Other observed reusable values are host-owned dummy plan mappings in settings
and a previewed MCP plan re-submitted in the recipe. API/help responses can
contain a plan, but response presence does not establish durable storage or
execution authority. The shipped frontend does not supply a durable saved-plan
store. Host-managed caches, exported results, long-lived catalog snapshots,
saved-query products and cross-version replay are **prospective** dependencies,
not verified consenting integrations. Do not infer them from a JSONField or a
schema accessor.

**Retain audit as provisional operational storage.** Do not replay an audit
metadata mapping as a complete plan. Treat even an opted-in complete plan, a
preview, or a host cache as untrusted: submit it to the current
`execute_plan(plan, request=current_request)` facade. Re-resolve the current
catalog, permissions, scope, budgets and bindings; parsing/validation at save
time is not authorization at execution time. Never persist compiler/prepared
state. [Facade tests](../tests/execution/test_facade.py),
[adapter revalidation](../tests/execution/test_adapter_revalidation.py) and the
MCP recipe cover fresh authorization; they do not promise arbitrary historical
payload conversion.

## Five-document decision: retain one unversioned draft

**Decision: retain** the current internal, draft, unfrozen, unversioned
`catalog`, `query-plan`, `capabilities`, `result`, and `error` documents, with no
negotiation or previous-shape handling. Their [schemas/accessors](internal-contracts.md)
are useful validation evidence, not a governed wire promise. The governed
`QueryResult.to_dict()` behavior and public error categories do not freeze
every nested representation or transport wrapper.

| Option evaluated | Benefit | Cost and disposition |
| --- | --- | --- |
| Retain one current draft | Matches observed same-artifact consumers, existing policy, schema tests and corpus; no new dispatch path. | Hosts must pin/retest provisional readers and revalidate stored plans. **Retain now.** |
| Add document version identifiers and previous-shape conversion | Could distinguish durable clients if incompatible historical consumers were demonstrated. | Requires a concrete semantic evolution policy, conversion/security review and new fixture matrix for all five documents; a label alone solves none of authorization, numeric or temporal mismatches. No such accepted need is evidenced here. **Defer, not approved.** |
| Runtime negotiation/profiles | Could select among independently supported implementations in a future design. | Adds handshake/downgrade behavior, failure modes and ongoing support costs without an observed consumer requirement. Contradicts the current rejection. **Do not implement.** |

[#199](https://github.com/revazi/django-asklens/issues/199) requests portability,
not identical Django/TypeScript convenience APIs. Semantic separation belongs to
[#200](https://github.com/revazi/django-asklens/issues/200); shared ownership,
version/evolution and second-implementation scope decisions belong to
[#205](https://github.com/revazi/django-asklens/issues/205), using actual
cross-implementation findings when available. This review neither blocks
ordinary Django fixes nor pre-decides those issues. There is no new standard,
second supported backend or smallest-common-denominator semantic policy.

## Narrow retain / change / defer conclusion

- **Retain** the exact governed subset and the observed provisional integration
  paths above, with their existing classifications. Provisional dependencies
  are real costs to maintain, not evidence for governing every helper.
- **Change documentation only:** make those costs and practical notices
  explicit. No runtime defect, accepted behavioral/API change, migration,
  contract expansion or deprecation is introduced by this review.
- **Defer** saved-query workflows, new registration helpers, adapter freezes,
  async/streaming and negotiation. They are not requirements discovered from
  these consumers. Do not file speculative implementation tickets as if they
  were accepted work. If a maintainer later accepts a concrete behavioral
  change, open a focused issue with the affected caller example, current versus
  proposed outcome, compatibility cost and regression cases **before** coding;
  shared-spec evolution remains coordinated with #205. Existing #188 owns the
  actual outstanding provider acceptance/lifecycle work.

## Practical notices and upgrade checks

These instructions operationalize the existing policy; they create no new
notice window or support tier. They apply to the **selected supported** core
entry points and shipped recipes above, not private compiler helpers or every
importable symbol.

1. For a planned governed change, name the exact import/call/result/error/event
   behavior, affected versions, replacement example and expected test outcome
   in a tracked issue and release notes. Nonurgent incompatibility does not
   belong in a `0.3.z` patch. There is **no fixed deprecation period**, and no
   promise of compatibility with `0.4.0` or 1.0. Do not log questions/plans or
   add runtime warnings simply to announce a documentation review.
2. For a selected provisional recipe change, include a before/after snippet
   (for example `payload["result"]["data"]`), affected extras/settings, safe
   failure handling and the installed-consumer test command in the same PR and
   release notes. Update all shipped readers together. Notice is practical
   migration help, not a newly guaranteed compatibility shim/window.
3. Security/privacy/authorization corrections may immediately reject unsafe
   behavior. Record affected behavior and safe mitigation without exploit or
   private diagnostic detail; never preserve unsafe scope or permission
   fallbacks for compatibility. Support-line retirement has its own
   [one-planned-release notice where safe and feasible](support-lifecycle.md#retirement-policy),
   not a new API deprecation rule.
4. Pin and authenticate the exact selected artifact. Public `0.3.1` is the
   immediate prior supported upgrade origin, public `0.3.0` an older checked
   origin, and `0.2.0` the older supported `0.2.x` origin; `0.1.0a1` is not one.
   Follow [installation](installation.md) and the
   [existing upgrade checklist](compatibility.md#upgrade-to-public-032). Record
   source-only example SHA separately from wheel version/digest. A local wheel
   bearing `0.3.2` is not the immutable public wheel.
5. Back up according to host policy, test on disposable data, run Django
   checks/migration checks, registrations, current-request revocation/scope,
   budgets, safe errors, audit and every enabled provisional adapter/provider.
   For persisted plans, test both success and denial through the **current
   facade**, including a permission removed since save/preview time. Never
   reuse a prepared query or assume a stored catalog grants access.
6. This review adds **no migration or data transformation**. Reverting its code
   does not require a reverse AskLens migration, but that is not a general
   rollback guarantee. Stop/drain old workers as appropriate; do not mix
   package/document/client versions or assume opted-in audit content, cached
   documents or provider behavior can be read by older code. Preserve host
   backups and retest the chosen rollback artifact; no previous-shape converter
   or mixed-version execution support is supplied.

## Verification and limits

Cross-check this inventory with the export/compatibility tests, installed typing
fixtures, normal core/API/admin/MCP consumer recipes and strict rendered docs.
The [maintenance roadmap](maintenance-roadmap.md#issues-191-and-192-contract-review-and-study-preparation)
records delivery checks separately from review/merge status. Passing these
checks establishes current synthetic behavior only, not independent adoption,
live-provider acceptance, production capacity, a completed first-run study or
security certification. No retired pilot or mandatory certification gate is
introduced.
