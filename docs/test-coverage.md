# Test coverage baseline and critical-boundary map

Status: informational repository evidence for STAB-2/SEC-5. This is not a
release gate, a security certification, or a claim of exhaustive behavior.
There is deliberately **no percentage threshold**.

Coverage measures only the `django_asklens` package. The configuration enables
branch measurement, includes package files that tests do not import, and reports
missing lines and partial branches. Coverage is a navigation aid: executing a
line or branch does not prove that its authorization, privacy, or semantic
invariants were asserted.

## Reproduce the baseline

From a development checkout with the locked development group installed:

```bash
uv sync --locked --group dev
bash scripts/coverage-baseline.sh
```

The script prints the current Git branch and commit, erases stale `.coverage`
data, runs the complete default SQLite suite, and prints the package report. It
passes no `--fail-under` value. The ignored `.coverage` data remains available
for local follow-up, for example:

```bash
uv run --no-sync coverage html
```

CI runs the same informational command in the Python 3.12 / Django 5.2 full-
suite matrix job. Other matrix jobs retain their ordinary test command.

## Recorded baseline

Recorded on 2026-08-16 from branch `stab2-sec5-coverage-baseline`, whose package
source was unchanged from base commit
`3930798cc54d08cb0a3775dbf29605c58bbe1230`. The local environment was Python
3.12.9, Django 6.1, and SQLite; live-provider tests remained disabled.

The complete working-tree suite result was `900 passed, 8 skipped`. The package
report was:

| Scope | Statements | Missed | Branches | Partial branches | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `django_asklens` total | 4,450 | 427 | 1,316 | 211 | 88% |

Representative critical modules make the baseline reviewable without implying
that one file represents an entire boundary:

| Boundary representative | Statements | Missed | Branches | Partial branches | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `execution/runner.py` | 145 | 12 | 12 | 1 | 92% |
| `api/views.py` | 101 | 5 | 22 | 2 | 94% |
| `mcp/core.py` | 112 | 4 | 36 | 5 | 94% |
| `admin_querying.py` | 24 | 7 | 4 | 2 | 68% |
| `catalog/registry.py` | 35 | 0 | 2 | 0 | 100% |
| `planning/validation.py` | 383 | 35 | 184 | 18 | 90% |
| `compiler/orm.py` | 130 | 3 | 24 | 3 | 96% |
| `results/serialization.py` | 101 | 8 | 56 | 5 | 89% |
| `execution/audit.py` | 104 | 9 | 24 | 4 | 90% |

These rounded values are a commit- and environment-bound starting point, not a
minimum. Future changes should inspect newly missing branches in the affected
boundary rather than optimize the aggregate percentage.

## Critical-boundary map

The map identifies primary source and regression surfaces. It does not replace
reading adjacent modules, test assertions, PostgreSQL evidence, or the security
model.

| Boundary | Primary package sources | Primary focused evidence | Review focus |
| --- | --- | --- | --- |
| Trusted execution facade | [`execution/runner.py`](../django_asklens/execution/runner.py), [`querying.py`](../django_asklens/querying.py) | [`test_facade.py`](../tests/execution/test_facade.py), [`test_context_revalidation.py`](../tests/execution/test_context_revalidation.py), [`test_internal_boundaries.py`](../tests/execution/test_internal_boundaries.py) | Current request/catalog/policy validation, context binding, safe execution errors, and no supported bypass. |
| Optional API adapter | [`api/views.py`](../django_asklens/api/views.py), [`api/serializers.py`](../django_asklens/api/serializers.py), [`api/permissions.py`](../django_asklens/api/permissions.py) | [`test_http_characterization.py`](../tests/api/test_http_characterization.py), [`test_error_adapter_regressions.py`](../tests/api/test_error_adapter_regressions.py), [`test_run_detail_privacy.py`](../tests/api/test_run_detail_privacy.py) | Route gates, strict input, safe envelopes, member/run opacity, audit effects, and application-data query rejection. |
| Optional MCP adapter | [`mcp/core.py`](../django_asklens/mcp/core.py), [`mcp/wrappers.py`](../django_asklens/mcp/wrappers.py), [`mcp/fastmcp.py`](../django_asklens/mcp/fastmcp.py) | [`test_core.py`](../tests/mcp/test_core.py), [`test_wrappers.py`](../tests/mcp/test_wrappers.py), [`test_mcp_example.py`](../tests/test_project/test_mcp_example.py) | Server-owned context mapping, facade convergence, compact discovery, and default row omission/denial. |
| Admin and frontend adapters | [`admin_querying.py`](../django_asklens/admin_querying.py), [`admin.py`](../django_asklens/admin.py), [`frontend/views.py`](../django_asklens/frontend/views.py) | [`test_admin_access.py`](../tests/test_admin_access.py), [`test_admin_view_only.py`](../tests/test_admin_view_only.py), [`test_demo_frontend.py`](../tests/test_project/test_demo_frontend.py) | Shared orchestration, view-only audit administration, permission gates, safe denials, and non-mutation. |
| Fail-closed scope | [`catalog/registry.py`](../django_asklens/catalog/registry.py), [`catalog/resources.py`](../django_asklens/catalog/resources.py), [`permissions.py`](../django_asklens/permissions.py) | [`test_scope_policy.py`](../tests/catalog/test_scope_policy.py), [`test_multitenant_security.py`](../tests/api/test_multitenant_security.py), [`test_complex_tenant_permissions.py`](../tests/api/test_complex_tenant_permissions.py) | Explicit global/context policy, trusted QuerySet providers, current identity, cross-scope isolation, and pre-application-SQL failure. |
| Structural budgets | [`planning/validation.py`](../django_asklens/planning/validation.py), [`planning/schemas.py`](../django_asklens/planning/schemas.py) | [`test_budgets.py`](../tests/planning/test_budgets.py), [`test_untrusted_plan_generative.py`](../tests/execution/test_untrusted_plan_generative.py) | Every bounded plan dimension, above-limit safe errors, audit privacy, and zero application-data SQL. |
| Private bindings and compilation | [`compiler/orm.py`](../django_asklens/compiler/orm.py), [`compiler/filters.py`](../django_asklens/compiler/filters.py), [`catalog/resources.py`](../django_asklens/catalog/resources.py) | [`test_orm.py`](../tests/compiler/test_orm.py), [`test_registry.py`](../tests/catalog/test_registry.py), [`test_public_errors.py`](../tests/execution/test_public_errors.py) | Semantic-to-private binding resolution, cardinality policy, prepared-state use, and non-disclosure of ORM/policy details. |
| Result serialization | [`results/serialization.py`](../django_asklens/results/serialization.py), [`results/presentation.py`](../django_asklens/results/presentation.py) | [`test_serialization.py`](../tests/results/test_serialization.py), [`test_presentation.py`](../tests/results/test_presentation.py), [`test_ordering_truncation.py`](../tests/execution/test_ordering_truncation.py) | Canonical safe values, deterministic metadata, empty results, presentation separation, ordering, and accurate truncation. |
| Audit privacy and lifecycle | [`execution/audit.py`](../django_asklens/execution/audit.py), [`management/_audit_lifecycle.py`](../django_asklens/management/_audit_lifecycle.py) | [`test_audit_boundary.py`](../tests/execution/test_audit_boundary.py), [`test_audit_lifecycle_commands.py`](../tests/management/test_audit_lifecycle_commands.py), [`test_audit_purge_command.py`](../tests/management/test_audit_purge_command.py) | Metadata-only defaults, server-owned sink/alias policy, failure isolation, safe output, preview defaults, and bounded explicit lifecycle operations. |

## Interpretation and limitations

- The recorded percentage is one local Python/Django/SQLite baseline. CI reruns
  the command on Python 3.12 / Django 5.2, but this report does not combine
  coverage from the complete compatibility matrix.
- The default run does not measure the PostgreSQL-marked execution paths as a
  PostgreSQL baseline. Existing PostgreSQL 15/18 jobs remain the evidence for
  database-sensitive semantics.
- Skipped live provider tests, the Compose/browser path, and installed-wheel
  smokes are separate opt-in or CI evidence. This run does not claim live
  provider, browser, transport, package-install, or installed-wheel coverage.
- Import-time execution can raise a module percentage without testing its public
  contract. Conversely, defensive or environment-specific code can remain
  unexecuted without being dead or unsafe.
- Aggregate coverage cannot prove zero-query rejection, cross-tenant isolation,
  fail-closed scope, privacy-safe audit, deterministic semantics, or adapter
  convergence; the focused assertions in the map carry those claims.
- This maintainer-operated synthetic evidence is not an independent security
  audit, production wire acceptance, external adoption evidence, or production-
  readiness certification.
- Choosing a threshold, expanding runtime behavior, or changing security policy
  requires separate authorization. This baseline has no percentage threshold.
