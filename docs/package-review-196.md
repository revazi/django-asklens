# Package review before the integration article

**Review date:** 2026-11-20 UTC. **Source baseline:**
[`6d0d15d9017749547eb8cc6bfdc59883561ff077`](https://github.com/revazi/django-asklens/tree/6d0d15d9017749547eb8cc6bfdc59883561ff077).
This is an AI-assisted, subsystem-by-subsystem source and assertion review for
[#196](https://github.com/revazi/django-asklens/issues/196), not an independent
security audit, release assessment, or approval to publish. Runtime source is
unchanged by this documentation work. The baseline was clean and synchronized
with `origin/main` before the review branch was created.

## Scope and method

Read `CONTRIBUTING.md`, `SECURITY.md`, the [compatibility policy](compatibility.md),
live #196/#183 and the existing #166/#168/#169 material. Inventoried the entire
`django_asklens` package, then followed the trust path from registration through
planning, execution and outward adapters. Inspected source implementations and
selected negative assertions, using the existing [critical-boundary map](test-coverage.md#critical-boundary-map),
[conformance corpus](conformance.md), [surface audit](internal-surface-leakage-audit.md)
and [integration review](integration-contract-review.md) as indexes, not as
proof that their conclusions cover every current combination.

The table distinguishes code inspection from regression evidence. Links below
refer to repository files; the baseline SHA above pins the reviewed runtime
and test bytes. Tests passing is supporting evidence only: it does not establish
that all policies, branches, combinations, or deployments are correct.

| Subsystem / risk | Source and symbols inspected | Assertion/evidence references and review result |
| --- | --- | --- |
| Public exports, registration and catalog — high trust impact | [`__init__.py`](../django_asklens/__init__.py), [`catalog/__init__.py`](../django_asklens/catalog/__init__.py), [`registry.py`](../django_asklens/catalog/registry.py): `CatalogRegistry.register`, `to_dict`; [`resources.py`](../django_asklens/catalog/resources.py): `SemanticResource.build`, field/enum/metric validation, `get_scope_queryset`; [`introspection.py`](../django_asklens/catalog/introspection.py); [`capabilities.py`](../django_asklens/catalog/capabilities.py) | [`test_registry.py`](../tests/catalog/test_registry.py), [`test_scope_policy.py`](../tests/catalog/test_scope_policy.py), [`test_export_surface.py`](../tests/test_export_surface.py). Explicit bindings and scope policy are necessary; serialization and execution are separate boundaries. Host-authored labels/descriptions/enums are intentional metadata disclosures, not automatically safe content. Private-policy triage remains a separate gate below. |
| Planner/provider/schema boundary — high | [`planner.py`](../django_asklens/planning/planner.py): `plan_question`; [`responses.py`](../django_asklens/planning/responses.py): `plan_asklens_response`, compact normalization; [`schemas.py`](../django_asklens/planning/schemas.py); [`llms/`](../django_asklens/llms/): dummy/factory, `OpenAICompatibleProvider.complete_json`, `strict_wire_schema`, `normalize_wire_response`; [`provider_preflight.py`](../django_asklens/provider_preflight.py) | [`test_planner.py`](../tests/planning/test_planner.py), [`test_responses.py`](../tests/planning/test_responses.py), [`test_openai_strict_schema.py`](../tests/llms/test_openai_strict_schema.py), [`test_provider_preflight.py`](../tests/llms/test_provider_preflight.py). Provider output remains untrusted. Strict-wire adaptation copies application schemas and retains invalid/unknown output for application rejection; this is offline evidence, not application/model wire acceptance. |
| Help, routing and prompt metadata — medium | [`intents.py`](../django_asklens/planning/intents.py): `route_question_intent`; [`help.py`](../django_asklens/planning/help.py): `validate_query_help`, suggestion-plan validation; [`optimization.py`](../django_asklens/planning/optimization.py); [`prompts.py`](../django_asklens/planning/prompts.py): catalog construction | [`test_help.py`](../tests/planning/test_help.py), [`test_intents.py`](../tests/planning/test_intents.py), [`test_routing.py`](../tests/execution/test_routing.py). Shortlisting is not authorization; suggestions/previews cannot authorize execution. This was not an evaluation of arbitrary wording or model quality. |
| Current-request facade, authorization, scope and budgets — high | [`runner.py`](../django_asklens/execution/runner.py): `execute_plan`, context construction, `_validate_untrusted_plan`, `_prepare_query_plan`, `_execute_compiled_query`; [`permissions.py`](../django_asklens/permissions.py); [`validation.py`](../django_asklens/planning/validation.py): payload/shape/count/value/relationship limits; [`querying.py`](../django_asklens/querying.py): shared orchestration | [`test_facade.py`](../tests/execution/test_facade.py), [`test_context_revalidation.py`](../tests/execution/test_context_revalidation.py), [`test_adapter_revalidation.py`](../tests/execution/test_adapter_revalidation.py), [`test_permission_resolution_failures.py`](../tests/execution/test_permission_resolution_failures.py), [`test_budgets.py`](../tests/planning/test_budgets.py). Fresh facade state is built after provider planning; parsed plans are reparsed. Scope is server-owned and lazy. Permission resolver failure cannot authorize fallback help. This does not make a host's cached Django permissions fresh or a faulty host scope provider correct. |
| Compiler, ORM semantics and ordering — high | [`orm.py`](../django_asklens/compiler/orm.py): context-bound prepared/compiled objects, list/group compilation, private aliases, identity tie-breaker and limit-plus-one fetch; [`filters.py`](../django_asklens/compiler/filters.py), [`aggregations.py`](../django_asklens/compiler/aggregations.py), [`dates.py`](../django_asklens/compiler/dates.py), [`temporal.py`](../django_asklens/planning/temporal.py) | [`test_orm.py`](../tests/compiler/test_orm.py), [`test_temporal_execution.py`](../tests/compiler/test_temporal_execution.py), [`test_internal_boundaries.py`](../tests/execution/test_internal_boundaries.py), [`test_ordering_truncation.py`](../tests/execution/test_ordering_truncation.py). Bindings/aggregate operations come from registration, not provider SQL. Cardinality and temporal semantics are constrained, not arbitrary analytics. Structural limits are not database cost/time guarantees. |
| Results, presentation and errors — high privacy / medium semantics | [`serialization.py`](../django_asklens/results/serialization.py): `serialize_rows`, canonical cells; [`presentation.py`](../django_asklens/results/presentation.py); `QueryResult.to_dict`; [`exceptions.py`](../django_asklens/exceptions.py): `public_error_payload`, fixed messages | [`test_serialization.py`](../tests/results/test_serialization.py), [`test_presentation.py`](../tests/results/test_presentation.py), [`test_public_errors.py`](../tests/execution/test_public_errors.py). Results require declared keys/types, with empty/truncated distinct. Presentation does not select data. Public errors must not be replaced by diagnostic exceptions in host code. |
| Audit, observability and lifecycle — high privacy | [`audit.py`](../django_asklens/execution/audit.py): policy resolution, metadata/content selection, sinks; [`observability.py`](../django_asklens/observability.py): eight-field event validation and transaction barrier; [`models.py`](../django_asklens/models.py), both [migrations](../django_asklens/migrations/); [`management/`](../django_asklens/management/): counts-only `check_asklens`, preview/execute redaction/purge and batch/alias validation | [`test_audit_boundary.py`](../tests/execution/test_audit_boundary.py), [`test_failure_audit_composition.py`](../tests/execution/test_failure_audit_composition.py), [`test_observability.py`](../tests/execution/test_observability.py), [`management tests`](../tests/management/). Metadata-only storage is not a guarantee that host/custom-sink exception logs contain no content. Audit sink failures do not widen access; delivery can fail. Observability is best effort, not a substitute for authoritative audit policy or host monitoring. |
| Optional API, admin and frontend — high | [`api/`](../django_asklens/api/): serializer allowlist, route-local error normalization, run-detail ownership/current privacy; [`access.py`](../django_asklens/access.py); [`admin.py`](../django_asklens/admin.py), [`admin_querying.py`](../django_asklens/admin_querying.py); [`frontend/views.py`](../django_asklens/frontend/views.py), [templates](../django_asklens/templates/) and selected JS rendering/network/storage paths | [`test_hostile_query_payloads.py`](../tests/api/test_hostile_query_payloads.py), [`test_run_detail_privacy.py`](../tests/api/test_run_detail_privacy.py), [`test_admin_view_only.py`](../tests/test_admin_view_only.py), [`test_demo_frontend.py`](../tests/test_project/test_demo_frontend.py), [installed recipe tests](../examples/quickstart/shop/). Data execution converges on shared orchestration/facade. A frontend page gate alone is not an API gate. Browser-local saved content and host logs need their own privacy review. No new browser capture or full browser-state audit was performed during this review. |
| Optional MCP — high | [`core.py`](../django_asklens/mcp/core.py): discovery, preview, execution and row omission/caps; [`wrappers.py`](../django_asklens/mcp/wrappers.py): trusted request factory; [`fastmcp.py`](../django_asklens/mcp/fastmcp.py): lazy SDK import and tool wiring | [`test_core.py`](../tests/mcp/test_core.py), [`test_omission_budgets.py`](../tests/mcp/test_omission_budgets.py), [`test_wrappers.py`](../tests/mcp/test_wrappers.py), [consumer recipe](../examples/quickstart/shop/mcp_recipe.py). Rows are omitted by default, not execution; host and per-call opt-in are both needed to return them. Server identity mapping remains host policy. In-process/mock evidence is not remote MCP security or interoperability acceptance. |
| Packaging, typing, installed consumers, CI and docs — medium | [`pyproject.toml`](../pyproject.toml), [`MANIFEST.in`](../MANIFEST.in), `py.typed`, [`contracts/`](../django_asklens/contracts/): schema generation/access; [`wheel-smoke.sh`](../.github/scripts/wheel-smoke.sh), [`quickstart_smoke.py`](../.github/scripts/quickstart_smoke.py), [`check-consumer-types.py`](../scripts/check-consumer-types.py), [CI workflows](../.github/workflows/), [`mkdocs.yml`](../mkdocs.yml) and [docs hooks](https://github.com/revazi/django-asklens/blob/6d0d15d9017749547eb8cc6bfdc59883561ff077/docs/mkdocs_hooks.py) | [`test_import_boundaries.py`](../tests/test_import_boundaries.py), [`test_optional_drf.py`](../tests/test_optional_drf.py), [`test_compatibility_contract.py`](../tests/test_compatibility_contract.py), [`test_consumer_typing_harness.py`](../tests/test_consumer_typing_harness.py), [`test_replay.py`](../tests/conformance/test_replay.py), [`test_showcase_and_docs_artifacts.py`](../tests/test_showcase_and_docs_artifacts.py). Optional dependency/import separation, installed byte checks and negative typing consumers are retained. Five schemas stay draft/unversioned; no second-backend conformance or governed-surface expansion follows. |

## Disposition and ranked follow-up

This public document is a scope/evidence index, **not a finding-free verdict**.
Security-sensitive observations and reproductions belong in the private
maintainer route specified by [SECURITY.md](https://github.com/revazi/django-asklens/blob/main/SECURITY.md),
not in this article, public issues, test logs or outreach. Private maintainer
triage is an open gate before external sharing; no unrelated runtime fix is
bundled with #196. An independently reviewed, focused follow-up is required
where triage confirms a defect. Ordinary policy obligations and missing external
evidence below are not presented as newly discovered vulnerabilities.

| Priority | Evidence-backed risk / required action | Classification |
| --- | --- | --- |
| High | Host identity, permission freshness, scope-provider correctness, safe registration metadata, DB privileges, timeouts and rate/concurrency policy remain essential. Review them in the actual host; never widen scope to recover from a failure. See [security](security-checklist.md) and [host controls](host-throttle-and-audit-controls.md). | Integration trust boundary; not discharged by internal tests. |
| High | Resolve private maintainer triage and obtain independent exact-head review before external claims or sharing. Do not interpret this report as security clearance. | Open review gate; no public sensitive reproduction. |
| Medium | [#188](https://github.com/revazi/django-asklens/issues/188) still lacks authorized live application/model acceptance. The tiny preflight and strict-schema mocks are not a successful live application integration. | Known evidence gap; not a new provider defect claim. |
| Medium | [#193](https://github.com/revazi/django-asklens/issues/193)/[#194](https://github.com/revazi/django-asklens/issues/194) sessions and representative application evidence do not exist. #195 findings cannot be invented from synthetic consumers. | Known usability/adoption gap. |
| Medium | Source/candidate improvements are newer than immutable public `0.3.2`; provisional adapters and draft documents need host upgrade tests. | Compatibility/evidence boundary, retained as documented. |
| Low | Sharing rules and public pages are mutable; unavailable channel rules block that channel. Awesome Django remains gated under #169. | Operational follow-up, not submission permission. |

## Verification and limits

On the unchanged baseline, the full default offline suite completed with
**1535 passed, 11 skipped** on Python 3.12.9 / Django 6.1 / SQLite. Live test and
demo consent were explicitly disabled and provider-key variables removed without
reading their values. Skips include opt-in live-provider and PostgreSQL-only
checks; they are not successful executions of those paths. Source inspection
and a bounded synthetic metadata/validation check informed private triage; no
production database, credentials, private application or live provider was
accessed. Subsequent #196 article/installed-wheel verification is recorded
separately, rather than retroactively attributed to this baseline review.

Limitations:

- This covers every package subsystem, not every line, interleaving, generated
  input, settings combination or downstream extension. Large help/capability and
  frontend modules were inspected by trust-path/helper selection, not audited
  exhaustively. Test assertions were sampled by invariant, not all reread.
- No independent penetration test, production/RLS/replica/router deployment,
  exhaustive permission-cache/concurrency analysis, remote MCP transport review,
  arbitrary provider-output/model-quality evaluation or second implementation.
- Local default SQLite evidence does not replace the hosted PostgreSQL/version
  matrix. Historical browser/showcase and public-artifact records are linked
  evidence, not newly replayed results from this review.
- No release/tag/upload, dependency change, workflow dispatch, deployment,
  recruitment, external contact or publication was performed. AI assistance and
  internal synthetic checks are not independent-user evidence.
