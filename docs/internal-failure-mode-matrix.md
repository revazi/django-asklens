# Issue #84 failure-mode and host-control matrix

## Status and scope

This internal matrix disposes the bounded concerns in issue #84 against `main` at
`2609c3c21db60cb6caec07c51457b1d91817be08`. It maps current implementation
and repository evidence; it does not change runtime behavior, settings, public
commands or APIs, audit policy, dependencies, migrations, CI infrastructure, or
wire documents.

The package remains read-only for registered application data. Its optional
built-in database audit writes and explicit operator lifecycle commands are
separate AskLens-owned effects. Structural budgets do not bound scan cost,
execution time, request lifetime, or concurrent load.

## Disposition labels

- **Already evidenced** — the concern has deterministic current tests and, where
  applicable, existing operator guidance.
- **Evidenced by PR #106** — the redaction-specific gap was added by PR #106 and
  is present on this matrix's base commit.
- **Deterministic tests-only addition** — this slice adds focused PostgreSQL
  evidence without changing package behavior or CI infrastructure.
- **Host-owned / unverifiable in package CI** — correctness depends on the
  deploying host's roles, proxy/server, topology, workload, or operating policy;
  repository tests cannot establish it as a package guarantee.
- **Confirmed runtime defect requiring a separate decision** — a reproduced
  current defect would stop this slice and require separately authorized runtime
  work.

## Failure-mode matrix

| ID | Concern | Disposition | Exact implementation, tests, or guidance | Remaining boundary |
| --- | --- | --- | --- | --- |
| FM-01 | Missing context; scope-provider exception, invalid/evaluated queryset, or wrong model | Already evidenced | [`test_scope_policy.py`](../tests/catalog/test_scope_policy.py) and [`test_public_errors.py`](../tests/execution/test_public_errors.py) assert fail-closed scope behavior before application-data SQL. | Host scope policy and membership correctness remain application-owned. |
| FM-02 | Unavailable application-query alias and broad fallback | Already evidenced | [`test_routing.py`](../tests/execution/test_routing.py) proves a server-owned queryset alias is retained and an invalid alias returns `asklens.execute.failed` without application SQL on another alias. | Host connection health, routing policy, replicas, and failover remain outside the package. |
| FM-03 | Invalid audit mode/content setting, sink import, or sink initialization | Already evidenced | [`test_audit_configuration_failures.py`](../tests/execution/test_audit_configuration_failures.py) proves safe binding errors, original parse-error preservation, zero SQL, and no fallback sink. | Hosts own deployment validation and availability of imported custom sinks. |
| FM-04 | Initial or refreshed permission resolver failure across executing adapters | Already evidenced | [`test_permission_resolution_failures.py`](../tests/execution/test_permission_resolution_failures.py) covers core orchestration, API, admin, MCP, all audit modes, safe errors, and no stale-permission help fallback. | Host authentication and permission backend availability remain host-owned. |
| FM-05 | Custom sink fails while recording a rejection or success | Already evidenced | [`test_audit_boundary.py`](../tests/execution/test_audit_boundary.py) proves rejection is preserved, success is not hidden or retried, and a rejected plan does not reach compilation. | Custom-sink durability, retry, alerting, retention, and repair are host operations. |
| FM-06 | Malformed, missing, unavailable, or missing-table built-in audit alias | Already evidenced | [`test_run_detail_privacy.py`](../tests/api/test_run_detail_privacy.py) proves server-owned write/read routing, no fallback write, success without a `run_id` when writing fails, and fixed safe `503` run-detail failure. Lifecycle table/introspection failures are covered by both management-command modules. | Real database outage drills, routing topology, FK availability, and recovery remain host-owned. |
| FM-07 | PostgreSQL `statement_timeout` supplied through Django connection `OPTIONS` | Deterministic tests-only addition | [`test_postgresql_host_controls.py`](../tests/execution/test_postgresql_host_controls.py) opens a disposable connection through the existing PostgreSQL settings pattern and verifies `SHOW statement_timeout` returns the synthetic configured value. | This checks option propagation only; it does not prove that PostgreSQL cancels a production query within a host SLO. |
| FM-08 | Statement-timeout cancellation, long scans, connection cleanup, and workload adequacy | Host-owned / unverifiable in package CI | [`production-checklist.md`](production-checklist.md), [`host-throttle-and-audit-controls.md`](host-throttle-and-audit-controls.md), and [`multitenancy-security.md`](multitenancy-security.md) require host verification. The repository uses no timing-dependent sleep to manufacture cancellation evidence. | Exercise representative indexed and adverse synthetic queries against the deployed pool/role/topology and monitor server-side cancellation and cleanup. |
| FM-09 | Dedicated PostgreSQL query role can read exposed data but cannot mutate application rows | Deterministic tests-only addition | [`test_postgresql_host_controls.py`](../tests/execution/test_postgresql_host_controls.py) creates a disposable `NOLOGIN`, non-superuser/non-creator role, grants only schema use plus `SELECT` on the synthetic query table, executes the real API/facade path, and proves an application update is denied. | The CI service account is intentionally privileged enough to create/drop the disposable role. Hosts must design and verify their own login role, grants, schemas, routers, and elevation controls. |
| FM-10 | Built-in database audit uses the same strict read-only query role | Deterministic tests-only addition | [`test_postgresql_host_controls.py`](../tests/execution/test_postgresql_host_controls.py) proves denied audit `INSERT` cannot replace either a successful API result or an opaque rejected-plan error; no audit row or `run_id` is produced. | A host requiring durable audit must choose approved custom/disabled audit behavior or separately routed writable audit storage; it must not grant application-data writes merely to make audit work. |
| FM-11 | End-to-end request timeout and proxy/ASGI cancellation | Host-owned / unverifiable in package CI | [`host-throttle-and-audit-controls.md`](host-throttle-and-audit-controls.md) and [`production-checklist.md`](production-checklist.md) require coordinated request/database limits and cancellation/connection-cleanup tests. | Request timeout and proxy/ASGI cancellation remain host-owned; AskLens adds no global timeout or cancellation protocol. |
| FM-12 | Request rate, queued work, and concurrent in-flight scans | Host-owned / unverifiable in package CI | [`host-throttle-and-audit-controls.md`](host-throttle-and-audit-controls.md) documents principal-bound DRF/proxy controls and equivalent MCP/Python guards. | Hosts own worker/semaphore budgets, throttling, saturation tests, monitoring, and capacity. |
| FM-13 | Lifecycle alias selection, table availability, privacy-safe output, and custom-sink isolation | Already evidenced | [`test_audit_lifecycle_commands.py`](../tests/management/test_audit_lifecycle_commands.py) and [`test_audit_purge_command.py`](../tests/management/test_audit_purge_command.py) cover configured aliases, selected-alias SQL, missing tables, bounded options, private-safe output, and no custom-sink invocation. | Operator authorization and direct ORM/database/custom administration remain host-owned. |
| FM-14 | Redaction preview, strict cutoff, bounded batches, field retention, and idempotence | Already evidenced | [`test_audit_lifecycle_commands.py`](../tests/management/test_audit_lifecycle_commands.py) covers point-in-time preview, zero preview writes, strict cutoff, exact fields cleared/retained, batching, idempotence, and SQLite/PostgreSQL execution. | Scheduling, retention selection, authorization, and reconciliation remain host-owned. |
| FM-15 | Redaction concurrent deletion and later eligible higher-PK insertion without a high-water bound | Evidenced by PR #106 | [`test_audit_lifecycle_commands.py`](../tests/management/test_audit_lifecycle_commands.py) proves zero-match continuation/count drift and that a later eligible higher-PK row can be included in the same run. | A prolonged run and preview/execute drift require host monitoring and reconciliation; this is not snapshot isolation. |
| FM-16 | Redaction later-batch rollback and earlier-batch partial progress | Evidenced by PR #106 | [`test_audit_lifecycle_commands.py`](../tests/management/test_audit_lifecycle_commands.py) injects a second-batch database failure, proves that batch rolls back, preserves the earlier commit, and checks private-safe failure output. | Operators must rerun preview, reconcile, and retry under host policy. |
| FM-17 | Purge high-water limit, concurrent deletion, and preview/execute count drift | Already evidenced | [`test_audit_purge_command.py`](../tests/management/test_audit_purge_command.py) covers the initial maximum-PK boundary, exclusion of later higher-PK rows, concurrent zero-delete continuation, and base-row rather than collector-total counts. | Lower/reused PKs and concurrent changes are not covered by a snapshot guarantee. |
| FM-18 | Purge collector relationships, `pre_delete`/`post_delete`, rollback, and partial progress | Already evidenced | [`test_audit_purge_command.py`](../tests/management/test_audit_purge_command.py) proves normal signals fire, a failing signal rolls back its batch, earlier committed deletion remains after a later failure, external effects remain visible, and `BaseException` is not converted. | Hosts must inspect cascades/protection/restriction and compensate external signal effects themselves. |
| FM-19 | Backup/restore, replicas, scheduling, legal retention, user/tenant deletion, and custom-sink lifecycle | Host-owned / unverifiable in package CI | [`production-checklist.md`](production-checklist.md) and [`host-throttle-and-audit-controls.md`](host-throttle-and-audit-controls.md) keep backups, replicas, scheduling, legal retention, and custom-sink operations explicit host responsibilities. | AskLens provides no scheduler, replica automation, universal deletion workflow, or legal-retention policy. |
| FM-20 | Production concurrency benchmark, production security certification, snapshot-isolation claim, or independent review | Host-owned / unverifiable in package CI | Current tests use synthetic repository data and representative PostgreSQL 15/18 jobs. PR #106 and this slice are maintainer-operated evidence. | No production certification, snapshot-isolation guarantee, or independent review is claimed; prerelease review remains deferred. |

## No current runtime-defect disposition

No current runtime defect was confirmed by this exact-main preflight or the new
PostgreSQL evidence. The historical audit-configuration and permission-resolver
defects identified through issue #82 were corrected in PRs #93 and #94 and are
now classified above as **Already evidenced**. Consequently, this slice makes no
runtime, setting, public API/command, dependency, migration, workflow-permission,
or audit-policy change.

The **Confirmed runtime defect requiring a separate decision** category therefore
has no current row. If remote representative PostgreSQL evidence contradicts the
verified behavior, stop rather than weakening a test or changing runtime under
this authorization.

## Host-owned verification checklist

Before production-like use, the deploying host should:

1. create migration/deployment and query credentials separately; verify the
   query role can select only intended schemas/tables and cannot perform DML,
   DDL, role creation, role elevation, or unrestricted cross-schema reads;
2. configure a role/connection-level PostgreSQL statement timeout and verify
   actual cancellation, server/pool connection recovery, monitoring, and a
   representative adverse synthetic workload in the deployed environment;
3. configure a coordinated, usually longer end-to-end request timeout and test
   proxy/ASGI cancellation, disconnected clients, worker cleanup, and database
   work termination;
4. select `AUDIT_MODE="disabled"` or an approved custom sink for a strict query
   connection, or validate a separately routed writable audit alias including
   migrations, referenced-user/FK topology, availability, and no fallback;
5. test database and audit outages through every enabled adapter while checking
   safe envelopes, no query retry, no broad alias fallback, and host alerts;
6. define rate/concurrency limits, indexes, capacity, backup/restore, replica
   consistency, retention, operator authorization, scheduling, legal handling,
   and custom-sink lifecycle/reconciliation procedures.

## Evidence limits

The added PostgreSQL tests use only synthetic rows, one disposable connection
setting, and a disposable role created by the existing privileged CI service
account. They add no second harness and no CI workflow change. Verifying a
session setting is not a query-cancellation timing test, and the synthetic role
is not a deployable grant template.

The lifecycle tests establish selected deterministic ORM/Django transaction
behavior, not snapshot isolation, a production concurrency benchmark, complete
host outage recovery, or compensation for external side effects. Repository CI
is not a production certification or external pilot evidence, and it is not an
independent review. Independent review remains deferred to prerelease review and
is not claimed complete.
