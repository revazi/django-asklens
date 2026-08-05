# Synthetic query performance baseline

This guide runs an opt-in AskLens performance baseline on the local synthetic
 test project. It is for local engineering comparison only, not a production
contract.

## Scope and safety

- Runs only against the test-project fixtures and seeded synthetic data.
- Uses a fixed reviewed query corpus and bounded iteration counts.
- Executes through `execute_asklens_query_request`, the same trusted path used by
  other demo entrypoints.
- Emits only a redacted artifact: wall/query timings, query counts, row counts,
  and summary metrics.
- Omits raw rows, SQL, provider payloads, credentials, tenant identifiers,
  questions, and permission details.
- Artifact shape/corpus/summary method are deterministic. Timestamps and measured
  timings are environment- and run-dependent.
- No runtime, API/schema, dependency, migration, package-public changes.
- No production, pilot, or security claim should be inferred from baseline
  artifacts.

## Prerequisites

- Docker Engine with Docker Compose.
- `uv`.
- PostgreSQL profile data seeded with `seed_complex_test_project`.

## One-command run

From repository root:

```bash
bash scripts/performance-baseline.sh
```

The script:

1. Boots a disposable compose project and PostgreSQL 18 service.
2. Verifies `POSTGRES` major version `18`.
3. Runs migrations and seeds data for a synthetic profile.
4. Executes `run_performance_baseline` with bounded warmups/iterations.
5. Writes a redacted JSON artifact.
6. Tears down the compose project, volume, and generated container state.

## Command options

- `--dataset-profile PROFILE` (or `--size PROFILE`, legacy alias):
  `small|medium|large` (default `medium`).
- `--query-profile compact|baseline` (default `baseline`).
- `--iterations N` (1..100, default `3`).
- `--warmups N` (0..20, default `1`).
- `--user USER` (default `admin`).
- `--artifact-dir DIR` (default `.asklens-performance-baseline`).
- `--artifact-name NAME` (default `latest`).
- `--output FILE` for explicit output path.
- `--commit HASH` for 40-character commit linkage; when omitted, defaults to
  `git rev-parse HEAD`.

## Default artifact name

Artifacts are written as:

```text
{artifact-name}-{query-profile}-size{dataset}-i{iterations}-w{warmups}.json
```

Example:

```text
.asklens-performance-baseline/latest-baseline-sizemedium-i3-w1.json
```

## Command and output shape

The script invokes:

```bash
python -m django run_performance_baseline \
  --user admin \
  --query-profile baseline \
  --iterations 1 \
  --warmups 1 \
  --dataset-profile medium \
  --artifact-dir .asklens-performance-baseline
```

The artifact shape/corpus/summary method are deterministic; the example below is from
**one local `baseline`/`medium` `1+1` run** and should be treated as a local
snapshot only (timings vary by machine/process state).

```json
{
  "evidence_kind": "synthetic_query_performance",
  "status": "success",
  "synthetic": true,
  "generated_at": "2026-08-05T12:34:56+00:00",
  "environment": {
    "python_version": "3.13.7",
    "django_version": "6.0.2",
    "database_vendor": "postgresql",
    "database_version": "18.4"
  },
  "dataset": {
    "profile": {
      "name": "medium",
      "scaled_tenant_count": 10,
      "members_per_tenant": 1000,
      "billing_months": 6,
      "schedule_weeks": 12,
      "batch_size": 1000
    },
    "counts": {
      "facilities": 12,
      "members": 10024,
      "billing_documents": 60144,
      "billing_lines": 102264
    }
  },
  "run_config": {
    "query_profile": "baseline",
    "dataset_profile": "medium",
    "iterations": {
      "measured": 1,
      "warmups": 1
    },
    "audit_mode": "custom_metadata_discard"
  },
  "cases": [
    {
      "name": "member-directory-truncated",
      "resource": "members",
      "intent": "list",
      "status": "success",
      "samples": [
        {
          "duration_ms": 3,
          "wall_duration_ms": 4.866,
          "query_count": 3,
          "row_count": 3
        }
      ],
      "duration_ms": {
        "count": 1,
        "min": 3,
        "p50": 3,
        "p95": 3,
        "max": 3,
        "mean": 3.0
      },
      "wall_duration_ms": {
        "count": 1,
        "min": 4.866,
        "p50": 4.866,
        "p95": 4.866,
        "max": 4.866,
        "mean": 4.866
      },
      "query_count": {
        "count": 1,
        "min": 3,
        "p50": 3,
        "p95": 3,
        "max": 3,
        "mean": 3.0
      },
      "row_count": {
        "count": 1,
        "min": 3,
        "p50": 3,
        "p95": 3,
        "max": 3,
        "mean": 3.0
      },
      "result_metadata": {
        "limit": 3,
        "limit_scope": "rows",
        "truncated": true
      },
      "audit": {
        "mode": "custom_metadata_discard",
        "event_count": 1
      }
    }
  ],
  "commit": "0123456789abcdef0123456789abcdef0123456789",
  "limitations": [
    "Synthetic dataset only; synthetic rows only.",
    "Host-dependent timing; wall and query durations are not SLA commitments.",
    "Single machine/process context only; cache warm-state may vary between runs.",
    "No production or pilot guarantee is implied by this artifact."
  ]
}
```

## Guidance

- Keep iterations bounded and scripts bounded to avoid long-running workloads.
- Use profile sizes (`small`, `medium`, `large`) with stable options to compare
  across runs. `large` is an explicit stress profile and can create millions of
  synthetic rows; use it for stress-only checks.
- `wall_duration_ms` is wall-clock milliseconds rounded to three decimals.
- `p50` and `p95` use nearest-rank semantics. At 1–3 measured samples this is a
  max-like smoke signal and not a statistically significant estimate.
- Use enough same-environment repetitions before comparing baselines. Treat values
  as directional diagnostics only and do not interpret them as SLAs.
