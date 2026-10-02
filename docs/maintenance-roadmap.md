# Post-0.2.0 maintenance roadmap

This is a prioritized engineering split, not a release promise or a substitute
for tracked review. It was prepared from the release workflow, support matrix,
coverage boundary map, production checklist, synthetic performance tooling, and
current documentation after publishing `0.2.0`. No open-source TODO/FIXME markers
were found in the Python, shell, workflow, or Markdown surfaces; the substantive
gaps are evidence and product-policy gaps described below.

## `0.2.1` candidates: compatible maintenance

These items should preserve the `0.2.x` public behavior and database shape. Each
still needs its own focused review.

### P0 — release integrity and security upkeep

1. **Land and rehearse the future release workflow without publishing.** Review
   `.github/workflows/publish.yml`, configure the `pypi` GitHub environment and
   the exact PyPI Trusted Publisher described in [Release process](releasing.md),
   and validate build/artifact handoff on a synthetic non-publishing workflow
   path. The first real use must remain environment-approved. Evidence: `0.2.0`
   required manual post-publication verification and the repository previously
   had CI but no publishing workflow.
2. **Keep dependency-advisory remediation current.** Run the locked `uv audit`
   job and update only affected locked dependencies when compatible; do not
   widen runtime majors merely to clear tooling output. Evidence: `0.2.0`
   already needed point-in-time PyJWT/urllib3 lock refreshes, and the production
   checklist says a failed advisory lookup is failed evidence rather than a
   silent pass.
3. **Add negative tests around release input and artifact handoff when the
   workflow changes.** Preserve exact tag/version equality, one wheel/one sdist,
   digest continuity, non-yanked PyPI selection, fixed download host, and OIDC
   isolation to the environment-protected job. Do not add `skip-existing` or a
   token fallback.

### P1 — confidence without contract changes

4. **Close focused missing-branch assertions in critical boundaries.** Start
   with permission-resolver invalid returns/exceptions, cross-adapter scope
   failure composition, and audit sink failure branches identified in
   [the coverage map](test-coverage.md). Review assertions, not an aggregate
   percentage; the project deliberately has no coverage threshold.
5. **Add a second operating-system smoke for packaging and path isolation.** CI
   currently demonstrates Linux behavior. A Windows or macOS core-wheel smoke
   would test path/temp/venv assumptions without changing the OS-independent
   package claim. PostgreSQL/Playwright can remain on Linux unless evidence
   justifies expansion.
6. **Refresh onboarding commands as executable documentation checks.** Keep the
   core and authenticated API quickstarts aligned with installation docs, ensure
   every probe runs outside the checkout, and assert copied commands remain
   secret-free and offline by default. Evidence: earlier package evidence was
   susceptible to repository metadata shadowing even though runtime bytes were
   correct.
7. **Reduce the typing baseline incrementally.** Type one trust boundary at a
   time and add focused mypy configuration only when that boundary is clean.
   Do not make mypy a global gate by suppressing the existing Django/DRF debt;
   `CONTRIBUTING.md` currently records that the full baseline is not clean.

### P2 — operational evidence maintenance

8. **Record comparable synthetic performance observations for changed query
   paths.** Use identical dataset/query profiles and review query count and
   wall-time directionally. Do not add unstable timing thresholds or call the
   result an SLA; the existing baseline is local synthetic evidence only.
9. **Keep release-specific evidence current.** On a patch candidate, update
   version assertions, package-content expectations, support statements, and
   immutable documentation links together. Retain explicit limitations for
   live providers, production capacity, independent security review, and the
   unsupported `0.1.0a1` testing artifact.

## `0.3.0` release work: feature or contract changes

These can alter supported behavior, policy, dependencies, or serialized/public
surfaces and therefore should not be slipped into a patch.

### P0 — explicit contract decisions

1. **Accepted for 0.3.x: a narrow governed core boundary.** Registration,
   trusted execution, public errors, and the typed observability event are named
   exactly in [the compatibility policy](compatibility.md). HTTP, MCP, admin,
   provider, broad helper, and document surfaces remain provisional/internal;
   schemas stay unversioned with no negotiation or previous-shape handling.
2. **Accepted for 0.3.0: an actionable bounded upgrade statement.** Supported
   `0.2.x` origins use normal host checks and require no migration for this
   scope; persisted plans always receive current-facade revalidation. There is
   no broad rollback promise, fixed deprecation window, or 1.0 stability claim.

### P1 — new runtime capabilities

3. **Evaluate first-class async execution or streaming only through the trusted
   facade.** It must preserve request identity, fail-closed scope, budgets,
   deterministic serialization, cancellation, and exactly-once audit semantics.
   An adapter-only bypass is unacceptable.
4. **Accepted for 0.3.0: dependency-free host observability.** The default-off
   typed callback has exact low-cardinality lifecycle semantics, excludes
   request/result/private content, runs after audit, and suppresses sink failure
   and reentrancy. External telemetry transports and production dashboards stay
   host-owned and are not package dependencies.
5. **Evaluate scheduled audit retention and richer export/deletion workflows.**
   Today scheduling, custom sinks, backups, replicas, and complete data-subject
   handling are host-owned. Automatic mutation, retries, or cross-store
   guarantees need explicit authorization, concurrency semantics, migrations,
   and operator documentation.
6. **Evaluate server-owned replica/routing policy helpers.** Current scope
   querysets may select a trusted alias, but AskLens intentionally does not parse
   aliases, monitor health, or fail over. A package-owned routing abstraction
   changes operational and consistency contracts.

### P2 — support expansion and external evidence

7. **Admit new Python, Django, PostgreSQL, DRF, or FastMCP lines only through the
   [support lifecycle](support-lifecycle.md).** Resolver success is insufficient;
   matrix, installed-artifact, PostgreSQL, reference-browser, metadata, and docs
   evidence must land together. Dropping a currently tested line requires the
   retirement process and notice where safe.
8. **Plan authorized live-provider and external evaluation.** Default CI must
   remain offline and secret-free. Representative-role live validation,
   independent security review, and external adoption evidence should be scoped
   and funded explicitly; synthetic fixtures must never be presented as those
   forms of evidence.
9. **Treat product features such as saved queries, custom production UI, and
   provider-specific adapters as host/product design.** Persisted plans must be
   revalidated through `execute_plan()`, and no feature may accept client-owned
   identity, permissions, tenant, bindings, or scope policy.

## Release assignment rule

A change belongs in `0.2.1` only when it is compatible, migration-free unless it
fixes an unavoidable defect, and does not widen accepted input or public policy.
Security fixes may fail closed immediately. New capabilities, public contracts,
support-line additions/removals, dependency-major changes, schema/versioning
policy, and operational automation belong in `0.3.0` unless a separately
reviewed security necessity requires earlier action.
