#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/coverage-baseline.sh

Run the complete default SQLite test suite with branch coverage for the
django_asklens package, then print an informational report. The command clears
stale coverage data first and enforces no percentage threshold.
EOF
}

if (($# != 0)); then
  usage >&2
  exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

commit="$(git rev-parse --verify HEAD)"
branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || printf 'detached')"
printf 'AskLens branch coverage baseline: branch=%s commit=%s\n' "$branch" "$commit"

uv run --no-sync coverage erase
uv run --no-sync coverage run -m pytest --strict-config --strict-markers
uv run --no-sync coverage report
