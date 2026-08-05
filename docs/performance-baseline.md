# Synthetic query performance baseline

This guide runs an opt-in AskLens performance baseline on the local synthetic test
project. It is for local engineering comparison only, not a production contract.

## Scope and safety

- Runs only against the test-project fixtures and seeded synthetic data.
- Uses a fixed reviewed query corpus and bounded iteration counts.
- Executes through `execute_asklens_query_request`, the same trusted path used by
  other demo entrypoints.
- Emits a redacted JSON artifact with deterministic structure and no raw rows,
  SQL, provider payloads, credentials, tenant identifiers, questions, or
  permission details.
- The payload is safe by design; timing and row metrics are benchmark observations
  and vary by environment and run.
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
3. Runs migrations and seeds synthetic data.
4. Executes `run_performance_baseline` with bounded warmups/iterations.
5. Writes a redacted JSON artifact.
6. Tears down containers, network, and container-managed volume on completion.

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
- `--commit HASH` for 40-character commit linkage; when omitted, defaults to `HEAD`.

## Artifact path

Artifacts are written as:

```text
{artifact-name}-{query-profile}-size{dataset_profile}-i{iterations}-w{warmups}.json
```

Example of a stable explicit invocation and deterministic artifact naming:

```bash
bash scripts/performance-baseline.sh \
  --query-profile baseline \
  --dataset-profile medium \
  --iterations 1 \
  --warmups 1 \
  --artifact-name final
```

This command produces:

```text
.asklens-performance-baseline/final-baseline-sizemedium-i1-w1.json
```

If you need a fixed output file, use `--output` and avoid inference from earlier
snapshot values.

## Artifact schema (closed shape)

The generated JSON keeps a fixed key set and value shape across all runs.
`generated_at`, measured timings, and summary statistics are all run-specific.
Use the artifact JSON itself as the source of truth for the specific run values.

### Top-level keys (fixed)

| Key | Type | Meaning |
| --- | --- | --- |
| `evidence_kind` | string | Always `"synthetic_query_performance"`. |
| `status` | string | Run status, currently `"success"` for completed baseline runs. |
| `synthetic` | boolean | Always `true` for synthetic-data-only baselines. |
| `generated_at` | string | UTC timestamp for artifact creation (varying per run). |
| `environment` | object | Safe runtime/server metadata. |
| `dataset` | object | Seed profile dimensions and resulting synthetic row counts. |
| `run_config` | object | Effective corpus, profile, and count configuration for the run. |
| `cases` | array | Exactly one per query case from the selected query profile. |
| `limitations` | array | Safety and interpretation notes for this artifact class. |
| `commit` | string | Lowercase 40-character commit SHA used for artifact lineage. |

### `environment`

| Key | Type | Meaning |
| --- | --- | --- |
| `python_version` | string | Runtime Python version used. |
| `django_version` | string | Runtime Django version used. |
| `database_vendor` | string | `sqlite` or `postgresql`. |
| `database_version` | string | Backend version string (for PostgreSQL, e.g. `18.4`). |

### `dataset`

#### `dataset.profile` (from `SEED_PROFILES`)

| Key | Type | Meaning |
| --- | --- | --- |
| `name` | string | Profile key (`small`, `medium`, `large`). |
| `scaled_tenant_count` | integer | Scaled tenants created by profile. |
| `members_per_tenant` | integer | Members created per scaled tenant. |
| `billing_months` | integer | Billing-month span used per synthetic member. |
| `schedule_weeks` | integer | Schedule horizon used per scaled tenant. |
| `batch_size` | integer | Bulk insert batch size. |

Concrete `medium` profile dimensions are:

```text
name=medium
scaled_tenant_count=10
members_per_tenant=1000
billing_months=6
schedule_weeks=12
batch_size=1000
```

#### `dataset.counts`

| Key | Type | Meaning |
| --- | --- | --- |
| `facilities` | integer | Facility rows visible in the seeded project. |
| `members` | integer | MemberProfile rows after seeding. |
| `billing_documents` | integer | BillingDocument rows after seeding. |
| `billing_lines` | integer | BillingLine rows after seeding. |

`counts` values are deterministic for a fixed seed and profile, but still tied to
runtime data shape and should be treated as measured output.

### `run_config`

| Key | Type | Meaning |
| --- | --- | --- |
| `query_profile` | string | Query corpus name (`compact` or `baseline`). |
| `dataset_profile` | string | Effective dataset profile used by run. |
| `iterations.measured` | integer | Measured sample count. |
| `iterations.warmups` | integer | Warmup sample count. |
| `audit_mode` | string | Always `custom_metadata_discard` for this script. |

### `cases` entry

`cases` contains one entry per query in the selected profile.

- `baseline` profile currently returns 3 cases.
- `compact` profile currently returns 1 case.

| Key | Type | Meaning |
| --- | --- | --- |
| `name` | string | Stable case identifier. |
| `resource` | string | Resource semantically queried. |
| `intent` | string | Query intent (`list` or `aggregate`). |
| `status` | string | Case status (`success` for completed runs). |
| `samples` | array | One element per measured sample. |
| `duration_ms` | object | Query summary for `duration_ms` samples. |
| `wall_duration_ms` | object | Query summary for wall-clock millisecond samples. |
| `query_count` | object | Summary of captured Django query-count samples. |
| `row_count` | object | Summary of returned row counts. |
| `result_metadata` | object | Result metadata fields from the core result serializer. |
| `audit` | object | Audit policy and event count metadata used by the run. |

#### `samples` entries

Each `samples` item contains exactly:

- `duration_ms` (integer)
- `wall_duration_ms` (float)
- `query_count` (integer)
- `row_count` (integer)

#### Summary objects

`duration_ms`, `wall_duration_ms`, `query_count`, and `row_count` summaries all
share this shape:

- `count`: number of measured samples.
- `min`: sample minimum.
- `max`: sample maximum.
- `p50`: nearest-rank 50th percentile.
- `p95`: nearest-rank 95th percentile.
- `mean`: arithmetic mean (rounded to 3 decimals for float summaries).

#### `result_metadata`

| Key | Type | Meaning |
| --- | --- | --- |
| `limit` | integer | Effective execution limit used for that case. |
| `limit_scope` | string | One of `rows` or `groups`. |
| `truncated` | boolean | Whether an additional row existed beyond the returned set. |

#### `audit`

| Key | Type | Meaning |
| --- | --- | --- |
| `mode` | string | Audit mode, currently `custom_metadata_discard`. |
| `event_count` | integer | Number of per-case audit events observed for measured samples. |

### Percentile method

`p50` and `p95` use nearest-rank semantics:

1. sort all measured values.
2. compute index `ceil(p/100 * n) - 1` (1-indexed nearest-rank position).
3. read the value at that index.

With very small sample counts this produces a max-like smoke signal; it is useful
for directional, deterministic comparisons, not statistical confidence bounds.

## Guidance

- Keep iterations bounded to keep local baseline runs practical and deterministic.
- Compare only with runs from the same profile and similar environment shape.
- Use `large` only for stress-only checks.
- Do not treat any measured value as an SLA.
- Use this artifact only as a local regression signal and evidence boundary checks.
- Keep command invocations stable across reruns when comparing baselines.
