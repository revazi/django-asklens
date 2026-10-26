#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

database="$root/.asklens-test-project.sqlite3"
if [[ -e "$database" ]]; then
  echo "Refusing to replace existing synthetic demo database: $database" >&2
  echo "Move it aside or follow the scoped cleanup in docs/test-project-demo.md." >&2
  exit 2
fi

command -v uv >/dev/null 2>&1 || {
  echo "uv is required. See docs/test-project-demo.md." >&2
  exit 1
}
uv run --no-sync python -c "import playwright.sync_api" >/dev/null || {
  echo "Playwright is missing. Run: uv sync --locked --group dev" >&2
  exit 1
}

port="$(uv run --no-sync python - <<'PY'
import socket
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    print(listener.getsockname()[1])
PY
)"
base_url="http://127.0.0.1:$port"
server_log="$(mktemp -t django-asklens-showcase.XXXXXX)"
server_pid=""

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  if ((exit_code != 0)) && [[ -s "$server_log" ]]; then
    echo "Demo server log (last 30 lines):" >&2
    tail -n 30 "$server_log" >&2
  fi
  rm -f "$server_log" "$database" "$database-shm" "$database-wal"
  exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings
export DJANGO_ASKLENS_DEMO_LIVE_LLM=0
export DJANGO_ASKLENS_LIVE_LLM=0

uv run --no-sync python -m django migrate --run-syncdb --noinput --verbosity 0
uv run --no-sync python -m django seed_complex_test_project --size small --verbosity 0
uv run --no-sync python -m django runserver --noreload "127.0.0.1:$port" \
  >"$server_log" 2>&1 &
server_pid=$!

uv run --no-sync python - "$port" "$server_pid" <<'PY'
import os
import socket
import sys
import time

port = int(sys.argv[1])
pid = int(sys.argv[2])
for _attempt in range(120):
    try:
        os.kill(pid, 0)
    except OSError:
        raise SystemExit("Demo server exited before capture.")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            break
    except OSError:
        time.sleep(0.25)
else:
    raise SystemExit("Demo server did not become ready within 30 seconds.")
PY

uv run --no-sync python scripts/capture-showcase.py --base-url "$base_url"
echo "PASS showcase capture complete; removing only the temporary synthetic database"
