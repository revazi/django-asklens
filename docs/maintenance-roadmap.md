# 0.3.x maintenance roadmap

This is a prioritized engineering split, not a release promise or a substitute
for tracked review. The immutable `v0.2.0`, `v0.3.0`, and `v0.3.1` tags,
releases, and public artifacts remain historical records and must not be moved,
recreated, or overwritten. The historical `0.1.0a1` package remains an
unsupported testing artifact, not an upgrade origin.

No future version or delivery date is promised here. Each change still requires
its own tracked review and exact-head evidence.

## Published `0.3.1` maintenance scope

`0.3.1` is the current published maintenance release: compatible,
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
   current public `0.3.1` wheel and source distribution must stay tied to
   independently recorded digests and immutable documentation. Local rebuilds
   remain separate evidence. Public `0.3.0` is the immediate prior supported
   upgrade origin, and `0.2.0` remains the older supported `0.2.x` origin.
6. **Maintain synthetic operational evidence.** Re-run package, Django,
   migration, PostgreSQL, and reference-browser checks when their affected paths
   change. Synthetic checks are not live-provider, production-capacity,
   deployment, adoption, or independent-security evidence.

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

The following categories are not `0.3.1` maintenance. They require tracked design
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
