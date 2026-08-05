#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/performance-baseline.sh [options]

  --dataset-profile PROFILE  Seed profile: small, medium, or large (default: medium).
  --size PROFILE            Legacy alias for --dataset-profile.
  --query-profile NAME      Baseline query profile: compact or baseline (default: baseline).
  --iterations N            Measured query iterations (default: 3, max 100).
  --warmups N               Warmup iterations (default: 1, max 20).
  --user USERNAME           Seeded demo user for baseline command (default: admin).
  --artifact-dir DIR        Artifact directory (default: .asklens-performance-baseline).
  --artifact-name NAME      Output artifact name without extension (default: latest).
  --output FILE             Exact output JSON path (overrides --artifact-dir/name).
  --commit HASH             Optional full 40-hex git commit SHA. Defaults to HEAD.
  --help                    Show this message.
EOF
}

validate_dataset_profile() {
  case "$1" in
    small|medium|large) return 0 ;;
    *)
      echo "Expected dataset profile small|medium|large, got: $1" >&2
      exit 2
      ;;
  esac
}

validate_query_profile() {
  case "$1" in
    compact|baseline) return 0 ;;
    *)
      echo "Expected --query-profile compact|baseline, got: $1" >&2
      exit 2
      ;;
  esac
}

validate_positive_int() {
  local value=$1
  local name=$2
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "Expected $name as a non-negative integer, got: $value" >&2
    exit 2
  fi
}

validate_int_range() {
  local value=$1
  local min=$2
  local max=$3
  local name=$4

  validate_positive_int "$value" "$name"
  if (( value < min || value > max )); then
    echo "Expected $name in [$min,$max], got: $value" >&2
    exit 2
  fi
}

validate_artifact_name() {
  local value=$1
  if ! [[ "$value" =~ ^[A-Za-z0-9._-]{1,80}$ ]]; then
    echo "artifact-name must match [A-Za-z0-9._-] (1-80 chars): $value" >&2
    exit 2
  fi
}

validate_commit_sha() {
  local value=$1
  if ! [[ "$value" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Expected 40-char lowercase commit SHA, got: $value" >&2
    exit 2
  fi
}

validate_output_path() {
  local value=$1
  if [[ -z "$value" ]]; then
    echo "--output requires a non-empty path." >&2
    exit 2
  fi
}

resolve_commit() {
  local provided=$1
  if [[ -n "$provided" ]]; then
    validate_commit_sha "$provided"
    printf '%s' "$provided"
    return 0
  fi

  local head
  if ! head=$(git rev-parse HEAD 2>/dev/null); then
    echo "Unable to resolve HEAD commit. Pass --commit explicitly." >&2
    exit 1
  fi
  if ! [[ "$head" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Current HEAD commit is not a valid 40-character hex value." >&2
    exit 1
  fi
  printf '%s' "$head"
}

run_performance() {
  local profile=$1
  local iterations=$2
  local warmups=$3
  local user=$4
  local dataset_profile=$5
  local artifact_dir=$6
  local artifact_name=$7
  local output_path=$8
  local commit=$9

  local args=(
    --user "$user"
    --query-profile "$profile"
    --iterations "$iterations"
    --warmups "$warmups"
    --dataset-profile "$dataset_profile"
    --artifact-dir "$artifact_dir"
    --artifact-name "$artifact_name"
  )

  if [[ -n "$output_path" ]]; then
    args+=(--output "$output_path")
  fi
  if [[ -n "$commit" ]]; then
    args+=(--commit "$commit")
  fi

  uv run --no-sync python -m django run_performance_baseline "${args[@]}"
}

seed_profile="medium"
query_profile="baseline"
iterations="3"
warmups="1"
user="admin"
artifact_dir=".asklens-performance-baseline"
artifact_name="latest"
artifact_path=""
commit=""

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
compose_file="$root/compose.yaml"

if [[ "$#" -gt 0 ]]; then
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --dataset-profile|--size)
        validate_dataset_profile "${2:?Missing dataset size value}"
        seed_profile="$2"
        shift 2
        ;;
      --query-profile)
        validate_query_profile "${2:?Missing --query-profile value}"
        query_profile="$2"
        shift 2
        ;;
      --iterations)
        validate_int_range "${2:?Missing --iterations value}" 1 100 "--iterations"
        iterations="$2"
        shift 2
        ;;
      --warmups)
        validate_int_range "${2:?Missing --warmups value}" 0 20 "--warmups"
        warmups="$2"
        shift 2
        ;;
      --user)
        if [[ -z "${2:?Missing --user value}" ]]; then
          echo "Expected --user value." >&2
          exit 2
        fi
        user="$2"
        shift 2
        ;;
      --artifact-dir)
        artifact_dir="$2"
        shift 2
        ;;
      --artifact-name)
        validate_artifact_name "${2:?Missing --artifact-name value}"
        artifact_name="$2"
        shift 2
        ;;
      --output)
        validate_output_path "${2:?Missing --output value}"
        artifact_path="$2"
        shift 2
        ;;
      --commit)
        validate_commit_sha "${2:?Missing --commit value}"
        commit="$2"
        shift 2
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        echo "Unknown option: $1" >&2
        usage >&2
        exit 2
        ;;
    esac
  done
fi

commit="$(resolve_commit "$commit")"

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required. See docs/test-project-demo.md." >&2
  exit 1
}
docker compose version >/dev/null 2>&1 || {
  echo "Docker Compose is required." >&2
  exit 1
}
command -v uv >/dev/null 2>&1 || {
  echo "uv is required. See docs/installation.md." >&2
  exit 1
}

docker_info_output() {
  docker info >/dev/null 2>&1
}
docker_info_output || {
  echo "Docker daemon is not available." >&2
  exit 1
}

compose() {
  docker compose --project-name "$COMPOSE_PROJECT_NAME" --file "$compose_file" "$@"
}

allocate_port() {
  uv run --no-sync python - <<'PY'
import socket

with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    print(listener.getsockname()[1])
PY
}

compose_project="django-asklens-baseline-$(id -u)-$$"
COMPOSE_PROJECT_NAME="$compose_project"
export COMPOSE_PROJECT_NAME

export DJANGO_SETTINGS_MODULE=tests.test_project.postgresql_demo_settings
export DJANGO_ASKLENS_POSTGRES_DB=asklens_demo
export DJANGO_ASKLENS_POSTGRES_USER=asklens_demo
export DJANGO_ASKLENS_POSTGRES_PASSWORD=asklens-demo-only
export DJANGO_ASKLENS_POSTGRES_HOST=127.0.0.1
export DJANGO_ASKLENS_POSTGRES_EXPECTED_MAJOR=18

# Reference smoke settings are live-provider disabled; keep baseline local-only.
export DJANGO_ASKLENS_DEMO_LIVE_LLM=0
export DJANGO_ASKLENS_LIVE_LLM=0
export DJANGO_ASKLENS_LIVE_LLM_LOG_IO=0

if [[ -z "$artifact_path" ]]; then
  artifact_path="$artifact_dir/${artifact_name}-${query_profile}-size${seed_profile}-i${iterations}-w${warmups}.json"
fi

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  if (( compose_started )); then
    if compose down --volumes --remove-orphans >/dev/null 2>&1; then
      echo "Tore down compose project $COMPOSE_PROJECT_NAME."
    else
      echo "Warning: compose teardown failed for $COMPOSE_PROJECT_NAME." >&2
    fi
  else
    echo "No compose project started for this run; nothing to tear down."
  fi

  if (( exit_code != 0 )) && [[ -n "${artifact_path:-}" ]]; then
    echo "Baseline failed. Artifact path was: $artifact_path" >&2
  fi
}

compose_started=0

trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

compose down --volumes --remove-orphans >/dev/null 2>&1 || true

PG_PORT="${ASKLENS_COMPOSE_POSTGRES_PORT:-$(allocate_port)}"
export ASKLENS_COMPOSE_POSTGRES_PORT="$PG_PORT"
export DJANGO_ASKLENS_POSTGRES_PORT="$PG_PORT"

export PG_PORT
uv run --no-sync python - <<'PY'
import os
import socket
import sys

port = int(os.environ["PG_PORT"])
with socket.socket() as listener:
    try:
        listener.bind(("127.0.0.1", port))
    except OSError:
        raise SystemExit(f"PostgreSQL host port {port} is unavailable.")
PY

compose config --quiet
[[ "$(compose config --images)" == "postgres:18" ]] || {
  echo "compose.yaml must use PostgreSQL 18 image." >&2
  exit 1
}

compose_started=1
compose up --detach --wait --wait-timeout 90 postgres

uv run --no-sync python - <<'PY'
import os

import psycopg

connection = psycopg.connect(
    dbname=os.environ["DJANGO_ASKLENS_POSTGRES_DB"],
    user=os.environ["DJANGO_ASKLENS_POSTGRES_USER"],
    password=os.environ["DJANGO_ASKLENS_POSTGRES_PASSWORD"],
    host=os.environ["DJANGO_ASKLENS_POSTGRES_HOST"],
    port=int(os.environ["DJANGO_ASKLENS_POSTGRES_PORT"]),
)
with connection:
    version_number = connection.info.server_version

if version_number // 10000 != 18:
    raise SystemExit(f"Baseline requires PostgreSQL 18, got: {version_number}")
PY

uv run --no-sync python -m django migrate --noinput --verbosity 0
uv run --no-sync python -m django migrate --run-syncdb --noinput --verbosity 0
uv run --no-sync python -m django seed_complex_test_project --size "$seed_profile" --verbosity 0

run_performance \
  "$query_profile" \
  "$iterations" \
  "$warmups" \
  "$user" \
  "$seed_profile" \
  "$artifact_dir" \
  "$artifact_name" \
  "$artifact_path" \
  "$commit"

if [[ ! -f "$artifact_path" ]]; then
  echo "Performance baseline did not emit an artifact at $artifact_path." >&2
  exit 1
fi

echo "Saved performance baseline artifact: $artifact_path"
echo "Baseline completed for profile=$query_profile dataset=$seed_profile iterations=$iterations warmups=$warmups"
