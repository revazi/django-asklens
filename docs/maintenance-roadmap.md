# 0.3.x maintenance roadmap

This is a prioritized engineering split, not a release promise or a substitute
for tracked review. The immutable `v0.2.0`, `v0.3.0`, `v0.3.1`, and `v0.3.2`
tags, releases, and public artifacts remain historical records and must not be moved,
recreated, or overwritten. The historical `0.1.0a1` package remains an
unsupported testing artifact, not an upgrade origin.

No future version or delivery date is promised here. Each change still requires
its own tracked review and exact-head evidence.

## Published `0.3.2` maintenance scope

`0.3.2` is the current published maintenance release: compatible,
migration-free work that hardens release operations and closes focused evidence
gaps without expanding package contracts. It remains an alpha maintenance
release.

### P0 — release integrity and security upkeep

1. **Keep Trusted Publishing recovery fail closed.** Use the protected `pypi`
   environment and its operator approval boundary. Diagnose publisher identity
   mismatches rather than bypassing them, and reuse preserved artifacts only
   under the bounded failed-job recovery procedure in the
   [release runbook](releasing.md#trusted-publisher-incident-and-recovery).
   Never use a token fallback, manual upload, `skip-existing`, tag replacement,
   or concealed retries.
2. **Keep dependency-advisory evidence current.** Run the locked `uv audit`
   command and report lookup failure as failed evidence. Update only an affected
   compatible lock entry when a concrete advisory justifies it; do not widen a
   runtime bound or dependency major for freshness.
3. **Preserve release handoff invariants.** Focused tests should retain exact
   tag/version equality, exactly one wheel and one source distribution, digest
   continuity from build through public verification, fixed PyPI hosts,
   non-yanked selection, and OIDC isolation to the environment-protected job.

### P1 — confidence without contract changes

4. **Close named trust-boundary composition gaps.** Prefer assertions for safe
   public outcomes, zero unauthorized application-data execution, metadata-only
   audit, and best-effort observability over aggregate coverage. There is no
   percentage threshold. Permission-resolution, cross-adapter scope, audit, and
   observability failures remain high-value review areas.
5. **Keep executable installation and provenance guidance current.** The
   current public `0.3.2` wheel and source distribution must stay tied to
   independently recorded digests and immutable documentation. Local rebuilds
   remain separate evidence. Public `0.3.1` is the immediate prior supported
   upgrade origin, `0.3.0` is an older checked origin, and `0.2.0` remains the
   older supported `0.2.x` origin.
6. **Maintain synthetic operational evidence.** Re-run package, Django,
   migration, PostgreSQL, and reference-browser checks when their affected paths
   change. Synthetic checks are not live-provider, production-capacity,
   deployment, adoption, or independent-security evidence.

### Issue #188: offline strict-schema gate only

The focused source/candidate repair resolves the reproduced offline
required/closed-object schema gate at the OpenAI-compatible provider boundary.
All emitted planner/compact-unified objects were already closed; the actual
mismatch was optional properties outside `required`. The earlier open-map
report referred to the unused full unified model schema, not its emitted compact
schema. Nullable wire omission markers and incoming normalization preserve the
existing application contracts and validation; open maps are rejected rather
than truncated. Mocked transports and synthetic credentials provide offline
schema/semantic evidence only. See the [exact mapping and limits](providers.md#offline-strict-schema-gate-resolved-live-acceptance-still-incomplete).

**Keep #188 open.** Authorized live application acceptance remains incomplete;
no provider API query, credential inspection or billed operation was performed.
The pinned snapshot's deprecation/shutdown and any replacement model-selection
and configuration/acceptance evidence are separate unresolved gates. The tiny
synthetic preflight cannot close them. No release, deployment, automatic retry,
model substitution, new public contract or dependency-PR change is included.

### Issue #189: registration guidance without a new helper

The [registration guide](registration.md#start-with-one-scoped-field) now starts
with a scoped one-field declaration and includes an executable
[before/after comparison and API decision](registration.md#beforeafter-less-presentation-boilerplate-same-policy).
Against baseline `f6ad3d2`, the quickstart's registration goes from 31 to 21
source lines, keeping all 10 keyword arguments; only two redundant labels are
removed. Nine of the original 12 field entries are mandatory binding/type/
nullability decisions. This is a reproducible structural measurement, not a
first-query timing or independent usability/adoption result.

Existing `register`, `CatalogRegistry`, `SemanticResource.build` and `Metric`
behavior already supplies presentation defaults and validation. No new helper,
public-contract change, permissive scope default, automatic model/field/choice
exposure, or migration is justified by this evidence. Resource timezone/scope,
private bindings, member permissions and metric cardinality stay explicit.
The expanded guide and compact source example use supported `0.3.x` behavior;
they do not change immutable public artifacts.

Local source/candidate verification: 722 focused registry/catalog/compiler/
planning/facade/compatibility/conformance/consumer tests passed (4 skipped), and
the full offline branch-coverage run passed 1,510 tests (11 live/PostgreSQL skips).
Regressions execute the documented examples, check before/after metadata and
private-policy equivalence, reject omitted enum choices/display labels, recheck
private metric permissions/current scope, and exercise invalid, duplicate,
missing and cached-import startup paths. Isolated installed-wheel core tutorial,
admin, API and MCP recipes passed, including source/wheel API-route parity.
Ruff, Django/migration checks, strict docs/rendered links, build/Twine/package
contents/exclusions and the locked audit also passed locally. These are synthetic
local checks, not hosted-check or independent-review approval, public artifact
authentication, live-provider acceptance, or production security certification.
Keep [#189](https://github.com/revazi/django-asklens/issues/189) open until its
focused PR has independent approval and hosted checks; no merge, release or
deployment is implied.

### Issue #190: bounded installed-wheel consumer typing

The source/candidate [typing inventory and limits](typing.md) follow the governed
registration, execution/result-access, public-error and observability boundary.
Existing inline annotations were sufficient; the only package typing change is
a `py.typed` marker. No duplicate stubs, runtime typing dependencies, annotation
rewrite, optional-adapter imports or runtime behavior changes are introduced.
A pinned development-only mypy group and copied outside-checkout consumers check
precise positive types and exactly 24 expected-negative diagnostics. CI runs the
bounded installed-wheel command; it does not claim repository-wide strict typing.
The single `django.db.models` missing-typing override cannot establish model or
queryset precision. Dynamic field mappings, request/scope internals, result cells
and draft document envelopes still require runtime validation; DRF/MCP adapters
remain optional/provisional.

Local synthetic verification: the installed candidate passes positive and exact
negative checks, including with checkout-shadowing environment variables set;
the same command also runs from the packaged sdist. The focused registry/catalog/
compiler/planning/facade/results/compatibility/conformance/import/consumer suite
passed 851 tests (4 skips). Full offline branch coverage passed 1,520 tests
(11 live/PostgreSQL skips), with no percentage gate. Isolated installed core
tutorial/admin, API and MCP recipes passed, including source/wheel API-route
parity. Ruff, Django/migration checks, strict docs/rendered-site validation,
build/Twine, CI package-content/exclusion/typing-dependency checks, and the locked
audit passed locally (120 audited packages, no known vulnerabilities or adverse
statuses). Lock changes only split/pin the existing mypy tool into its own group;
no resolved package version or runtime dependency changed.

[#190](https://github.com/revazi/django-asklens/issues/190) is closed following
independent approval and all 16 hosted PR checks in
[PR #215](https://github.com/revazi/django-asklens/pull/215), merged at
`1188e981b5fb4fba468f7ecfcf97e0886aa22874`; exact-merge CI, docs and CodeQL
also passed. These checks are not public-artifact authentication, live-provider
acceptance, production security certification, a release or a deployment.

### Issues #191 and #192: contract review and study preparation

The [evidence-linked integration review](integration-contract-review.md) records
observed imports/settings, HTTP/MCP and frontend/provider dependencies, and
actual audit/dummy/preview-plan reuse. It distinguishes repository-operated
synthetic consumers from prospective integrations; no consenting external or
executed TypeScript consumer evidence is asserted. Retain decisions preserve
the existing governed subset and provisional adapters. The five internal
unversioned draft documents remain unchanged, with no negotiation or
previous-shape handling. Practical notices, current-facade revalidation and
upgrade/rollback limits apply existing policy, not a new deprecation window.
No accepted runtime/API change, migration or speculative redesign is introduced;
shared-spec evolution remains with #200/#205, live provider gates with #188.

The [first-run study protocol and result instrument](first-run-study.md) select
the authenticated public `0.3.2` wheel plus exact source example SHA, with a
one-file blank-registration task variant so registration effort is observable.
It defines neutral unassisted work, scoped Alice/Bob success and safe denial,
explicit timing/assistance criteria, privacy/retention, independent-participant
eligibility and focused triage. Ten minutes is a hypothesis only. Source files
and protocol revision are separate identities from the public package.

Local verification for this documentation/test-only slice: **1,522 passed,
11 skipped** in the standard full offline suite (live providers and optional
PostgreSQL service skipped). Focused compatibility/export/import/schema/audit/
adapter revalidation checks passed (115 tests), as did focused example/study/
consumer checks (70 tests). Installed candidate core tutorial/admin, API and
MCP recipes, source/wheel API-route parity, positive typing plus 24 exact
negative diagnostics, strict docs/rendered-site validation (40 pages), Ruff
lint/format (279 files), Django/migration checks, build/Twine and CI package
contents/exclusions passed. The unchanged lock's audit resolved 121 packages
and reported no known vulnerabilities/adverse statuses in 120 audited packages.

A separate **maintainer rehearsal**, not an independent session, authenticated
the exact public wheel/sdist and used the pinned source example outside the
checkout (Python 3.12.9, macOS arm64, Django 6.1.3, Pydantic 2.14.3). The blank
registration produced an empty registry; restoring the reviewed declaration
then passed migrations/checks, scoped Alice/Bob commands, opaque nonzero denial,
all nine example tests and host migration-drift checks. Import provenance and
absence of DRF/FastMCP were checked. No human registration effort or first-query
time was measured; scripted restoration is not task completion by a participant.
These results do not authenticate a candidate as the public artifact or prove
production transport/provider acceptance, adoption or security certification.
No runtime, dependency, lock, migration, release or deployment change is made.

**Delivery status:** #191 is closed following independent review and all 16
hosted PR checks in [PR #216](https://github.com/revazi/django-asklens/pull/216),
merged at `27a1e3e1f1b2286f8b079fecdfb10363b4da17d9`; exact-merge CI, docs and
CodeQL also passed. On **2026-11-18 UTC**, the maintainer explicitly **approved**
the [exact protocol at that commit](https://github.com/revazi/django-asklens/blob/27a1e3e1f1b2286f8b079fecdfb10363b4da17d9/docs/first-run-study.md),
satisfying #192's final maintainer-review criterion for protocol preparation
only. Worker review/CI are not substitutes for that decision. #193's recruitment
route, participant contact, consent process, recording, custodian/storage setup
and actual sessions remain separately unauthorized and incomplete. No study or
independent usability result is claimed.

### Point-in-time locked dependency audit

At `2026-10-04T09:31:52Z`, the following exact command completed successfully
against the unchanged `uv.lock`:

```bash
uv audit --locked --preview-features audit-command
```

It resolved 109 locked packages and reported no known vulnerabilities and no
adverse project statuses in the 108 audited packages. No advisory remediation,
dependency update, runtime-bound change, or major-version widening was justified,
so the lock remains unchanged. This is a point-in-time advisory lookup, not
production or independent security certification; a future lookup failure must
be reported as failed evidence rather than treated as a pass.

### Second-operating-system package-smoke decision

A bounded macOS or Windows core-wheel isolation job was evaluated for this
maintenance slice and is **deferred**, not silently assumed. The exact-head CI
matrix already builds and installs the wheel outside the checkout on Linux for
core, API, and MCP across supported Python/Django combinations, and the candidate
package job adds isolated source-wheel and upgrade evidence. No OS-specific path,
temporary-directory, or virtual-environment defect motivated another runner.

A macOS core-only job would duplicate a smaller subset while adding hosted-runner
and package-resolution maintenance; a Windows job would first require a separate
review of the Bash-based smoke harness rather than weakening it. Reconsider a
second OS when an OS-specific defect, a portable bounded harness, or a support
policy change supplies a concrete invariant. Existing Linux/PostgreSQL and
Playwright coverage must not be reduced to fund it.

## Separately reviewed future-minor work

The following categories are not compatible `0.3.x` maintenance. They require tracked design
and compatibility review in a future minor line; this roadmap assigns neither a
version nor a delivery date.

### Contract and capability design

- Async execution, streaming, and cancellation semantics through the trusted
  facade, including current identity, fail-closed scope, budgets, deterministic
  serialization, and exactly-once authoritative audit behavior.
- Package-owned replica selection, routing, health checking, or failover.
- Saved queries or other product workflow that persists plans or client-facing
  policy. Stored plans would still require current-facade revalidation.
- Document/schema versioning, negotiation, or previous-shape handling for the
  five current AskLens documents.
- New public helpers, adapter contracts, event fields/names, or other governed
  surface changes.

### Operational and support-policy design

- Scheduled audit retention, automatic mutation/retries, richer export/deletion
  workflows, or cross-store guarantees.
- External telemetry transports, SDKs, dashboards, or dependencies. Current
  observability remains default-off, dependency-free, content-free,
  best-effort, reentrancy-safe, and distinct from authoritative audit.
- Python, Django, PostgreSQL, DRF, or FastMCP support-line additions/removals, or
  dependency-major policy changes, under the
  [support lifecycle](support-lifecycle.md).
- Authorized live-provider, external-adoption, production-capacity, or
  independent-security evaluation. Offline synthetic fixtures cannot stand in
  for those forms of evidence.

## Preserved 0.3.x boundary

The narrow governed boundary remains exactly the documented registration and
resource APIs, trusted `execute_plan()` / `QueryResult`, namespaced public
errors, and privacy-safe host observability described in the
[compatibility policy](compatibility.md). This is not a 1.0 stability claim.

HTTP/DRF, MCP, admin, frontend, provider orchestration and internals, broad
helpers, settings outside the governed observability behavior, and operational
audit storage remain provisional or internal where currently documented. The
five `catalog`, `query-plan`, `capabilities`, `result`, and `error` documents and
their schemas remain draft, internal, unversioned, and without negotiation.

A compatible `0.3.1` change must add no migration, must not widen accepted policy
or weaken fail-closed behavior, and must not alter an immutable historical
artifact. Security or privacy defects may still require a separately reviewed,
immediate fail-closed correction. New capabilities, contract changes,
support-line changes, dependency-major changes, schema/version policy, and
operational automation remain future-minor work.
