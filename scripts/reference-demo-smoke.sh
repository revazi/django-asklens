#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/reference-demo-smoke.sh [--smoke|--manual|--teardown|--help]

  --smoke     Rebuild the synthetic PostgreSQL 18 database, run the committed
              Playwright/Chromium evidence, and tear everything down (default).
  --manual    Rebuild and seed the database, then run the MCP-enabled demo until
              Ctrl-C; teardown runs automatically.
  --teardown  Remove only the fixed manual-demo Compose project's containers,
              network, and named volumes.
EOF
}

mode="smoke"
case "${1:-}" in
  ""|--smoke) ;;
  --manual) mode="manual" ;;
  --teardown) mode="teardown" ;;
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
if (($# > 1)); then
  echo "Expected at most one option." >&2
  usage >&2
  exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$root/compose.yaml"
cd "$root"

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required. See docs/test-project-demo.md." >&2
  exit 1
}
docker compose version >/dev/null 2>&1 || {
  echo "The Docker Compose plugin is required." >&2
  exit 1
}

manual_project="${DJANGO_ASKLENS_COMPOSE_PROJECT:-django-asklens-reference-demo}"
if [[ "$mode" == "smoke" ]]; then
  COMPOSE_PROJECT_NAME="django-asklens-reference-smoke-$(id -u)-$$"
else
  COMPOSE_PROJECT_NAME="$manual_project"
fi
case "$COMPOSE_PROJECT_NAME" in
  django-asklens-reference-*) ;;
  *)
    echo "Refusing non-AskLens Compose project name: $COMPOSE_PROJECT_NAME" >&2
    exit 2
    ;;
esac
export COMPOSE_PROJECT_NAME

compose() {
  docker compose --project-name "$COMPOSE_PROJECT_NAME" --file "$compose_file" "$@"
}

if [[ "$mode" == "teardown" ]]; then
  compose down --volumes --remove-orphans
  echo "Removed Compose project $COMPOSE_PROJECT_NAME."
  exit 0
fi

command -v uv >/dev/null 2>&1 || {
  echo "uv is required. See docs/test-project-demo.md." >&2
  exit 1
}
docker info >/dev/null 2>&1 || {
  echo "The Docker daemon is not available." >&2
  exit 1
}

allocate_port() {
  uv run --no-sync python - <<'PY'
import socket

with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    print(listener.getsockname()[1])
PY
}

port_is_available() {
  uv run --no-sync python - "$1" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as listener:
    try:
        listener.bind(("127.0.0.1", port))
    except OSError:
        raise SystemExit(1)
PY
}

ASKLENS_COMPOSE_POSTGRES_PORT="${ASKLENS_COMPOSE_POSTGRES_PORT:-$(allocate_port)}"
DJANGO_ASKLENS_DEMO_PORT="${DJANGO_ASKLENS_DEMO_PORT:-$(allocate_port)}"
export ASKLENS_COMPOSE_POSTGRES_PORT

server_pid=""
server_log="$(mktemp -t django-asklens-reference-server.XXXXXX)"
compose_started=0

stop_server() {
  if [[ -z "$server_pid" ]] || ! kill -0 "$server_pid" 2>/dev/null; then
    return
  fi
  kill "$server_pid" 2>/dev/null || true
  for _attempt in {1..20}; do
    if ! kill -0 "$server_pid" 2>/dev/null; then
      wait "$server_pid" 2>/dev/null || true
      return
    fi
    sleep 0.1
  done
  kill -KILL "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  stop_server
  if ((compose_started)); then
    compose down --volumes --remove-orphans >/dev/null 2>&1 || {
      echo "Warning: Compose teardown for $COMPOSE_PROJECT_NAME failed." >&2
    }
  fi
  if ((exit_code != 0)) && [[ -s "$server_log" ]]; then
    echo "Demo server log (last 40 lines):" >&2
    tail -n 40 "$server_log" >&2
  fi
  rm -f "$server_log"
  exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# A fixed manual project can be safely reset; smoke project names are unique.
compose down --volumes --remove-orphans >/dev/null 2>&1 || true
port_is_available "$ASKLENS_COMPOSE_POSTGRES_PORT" || {
  echo "PostgreSQL host port $ASKLENS_COMPOSE_POSTGRES_PORT is unavailable." >&2
  exit 1
}
port_is_available "$DJANGO_ASKLENS_DEMO_PORT" || {
  echo "Demo host port $DJANGO_ASKLENS_DEMO_PORT is unavailable." >&2
  exit 1
}
compose config --quiet
[[ "$(compose config --images)" == "postgres:18" ]] || {
  echo "compose.yaml must use the PostgreSQL 18 image." >&2
  exit 1
}

export DJANGO_SETTINGS_MODULE=tests.test_project.postgresql_demo_settings
export DJANGO_ASKLENS_POSTGRES_DB=asklens_demo
export DJANGO_ASKLENS_POSTGRES_USER=asklens_demo
export DJANGO_ASKLENS_POSTGRES_PASSWORD=asklens-demo-only
export DJANGO_ASKLENS_POSTGRES_HOST=127.0.0.1
export DJANGO_ASKLENS_POSTGRES_PORT="$ASKLENS_COMPOSE_POSTGRES_PORT"
export DJANGO_ASKLENS_POSTGRES_EXPECTED_MAJOR=18
# PostgreSQL demo settings hard-disable providers/rows; these remain defense-in-depth.
export DJANGO_ASKLENS_LIVE_LLM=0
export DJANGO_ASKLENS_DEMO_LIVE_LLM=0
export DJANGO_ASKLENS_LIVE_LLM_LOG_IO=0
export DJANGO_ASKLENS_MCP_ENABLED=1
export DJANGO_ASKLENS_MCP_USERNAME=facility-owner
export DJANGO_ASKLENS_MCP_EXPOSE_QUERY=0
export DJANGO_ASKLENS_MCP_ALLOW_ROWS=0

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
    port=os.environ["DJANGO_ASKLENS_POSTGRES_PORT"],
)
with connection, connection.cursor() as cursor:
    cursor.execute("SHOW server_version_num")
    version_number = int(cursor.fetchone()[0])
if version_number // 10_000 != 18:
    raise SystemExit("Reference demo requires PostgreSQL major version 18.")
print("PASS PostgreSQL 18 health and server-version guard")
PY

# Apply migrated apps first so PostgreSQL can resolve test-project auth FKs when
# the intentionally migration-free synthetic app is synced in the second pass.
uv run --no-sync python -m django migrate --noinput --verbosity 0
uv run --no-sync python -m django migrate --run-syncdb --noinput --verbosity 0
uv run --no-sync python -m django seed_complex_test_project --size small --verbosity 0

echo "PASS migrated and seeded the synthetic Django reference app"
base_url="http://127.0.0.1:$DJANGO_ASKLENS_DEMO_PORT"

if [[ "$mode" == "manual" ]]; then
  echo "Synthetic demo: $base_url/"
  echo "FastMCP endpoint: $base_url/mcp"
  echo "Press Ctrl-C to remove only Compose project $COMPOSE_PROJECT_NAME."
  uv run --no-sync uvicorn tests.test_project.demo_asgi:application \
    --host 127.0.0.1 --port "$DJANGO_ASKLENS_DEMO_PORT"
  exit 0
fi

uv run --no-sync python -c "import playwright.sync_api" || {
  echo "Playwright is not installed. Run: uv sync --locked --group dev" >&2
  exit 1
}
uv run --no-sync uvicorn tests.test_project.demo_asgi:application \
  --host 127.0.0.1 --port "$DJANGO_ASKLENS_DEMO_PORT" \
  >"$server_log" 2>&1 &
server_pid=$!

uv run --no-sync python - "$DJANGO_ASKLENS_DEMO_PORT" "$server_pid" <<'PY'
import os
import socket
import sys
import time

port = int(sys.argv[1])
server_pid = int(sys.argv[2])
for _attempt in range(120):
    try:
        os.kill(server_pid, 0)
    except OSError:
        raise SystemExit("Demo ASGI server exited before readiness.")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            break
    except OSError:
        time.sleep(0.25)
else:
    raise SystemExit("Demo ASGI server did not become ready within 30 seconds.")
PY

uv run --no-sync python tests/e2e/reference_demo.py --base-url "$base_url"
echo "PASS reference demo smoke; cleanup follows"
