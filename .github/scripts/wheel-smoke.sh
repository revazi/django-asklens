#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mode="${1:?usage: wheel-smoke.sh <core|api|mcp> <django-package> <django-version-prefix>}"
django_package="${2:?usage: wheel-smoke.sh <core|api|mcp> <django-package> <django-version-prefix>}"
django_version_prefix="${3:?usage: wheel-smoke.sh <core|api|mcp> <django-package> <django-version-prefix>}"

case "$mode" in
  core)
    extra=""
    ;;
  api)
    extra="[api]"
    ;;
  mcp)
    extra="[mcp]"
    ;;
  *)
    echo "Unsupported wheel smoke mode: $mode" >&2
    exit 2
    ;;
esac

smoke_venv="$(mktemp -d)"
cleanup() {
  rm -r "$smoke_venv"
}
trap cleanup EXIT
python -m venv "$smoke_venv"
wheel="${4:-}"
if [[ -z "$wheel" ]]; then
  wheel="$(echo "$project_root"/dist/django_asklens-*.whl)"
fi
if [[ ! -f "$wheel" ]]; then
  echo "Wheel does not exist: $wheel" >&2
  exit 2
fi
"$smoke_venv/bin/python" -m pip install --quiet --upgrade pip
"$smoke_venv/bin/python" -m pip install --quiet "$django_package"
"$smoke_venv/bin/python" -m pip install --quiet "${wheel}${extra}"
DJANGO_VERSION_PREFIX="$django_version_prefix" \
  "$smoke_venv/bin/python" "$project_root/.github/scripts/wheel_smoke.py" "$mode"

source_snapshot="${ASKLENS_SOURCE_API_SNAPSHOT:-}"
if [[ "$mode" == "api" && -n "$source_snapshot" ]]; then
  if [[ ! -f "$source_snapshot" ]]; then
    echo "Source API route snapshot does not exist: $source_snapshot" >&2
    exit 2
  fi
  source_snapshot="$(cd "$(dirname "$source_snapshot")" && pwd)/$(basename "$source_snapshot")"
  wheel_snapshot="$smoke_venv/installed-wheel-api-routes.json"
  (
    cd "$smoke_venv"
    env -u PYTHONPATH "$smoke_venv/bin/python" \
      "$project_root/.github/scripts/api_route_snapshot.py" \
      --provenance wheel \
      --source-root "$project_root" \
      --output "$wheel_snapshot"
    env -u PYTHONPATH "$smoke_venv/bin/python" \
      "$project_root/.github/scripts/api_route_snapshot.py" \
      --compare "$source_snapshot" "$wheel_snapshot"
  )
fi
