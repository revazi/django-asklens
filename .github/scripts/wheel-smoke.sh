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
wheel="$(cd "$(dirname "$wheel")" && pwd)/$(basename "$wheel")"
"$smoke_venv/bin/python" -m pip install --quiet --upgrade pip
"$smoke_venv/bin/python" -m pip install --quiet "$django_package"
"$smoke_venv/bin/python" -m pip install --quiet "${wheel}${extra}"
(
  cd "$smoke_venv"
  env -u PYTHONPATH \
    DJANGO_VERSION_PREFIX="$django_version_prefix" \
    ASKLENS_FORBIDDEN_SOURCE_ROOT="$project_root" \
    "$smoke_venv/bin/python" "$project_root/.github/scripts/wheel_smoke.py" "$mode"
)

# Opt in only for the current candidate core CI path. Historical published
# upgrade probes also use this installer and must not inherit a newer tutorial.
case "${ASKLENS_TUTORIAL_SMOKE:-0}" in
  0) ;;
  1)
    if [[ "$mode" != "core" ]]; then
      echo "The public tutorial requires a core-only wheel environment." >&2
      exit 2
    fi
    (
      cd "$smoke_venv"
      env -u PYTHONPATH -u PYTHONHOME -u DJANGO_SETTINGS_MODULE \
        "$smoke_venv/bin/python" -s \
        "$project_root/.github/scripts/quickstart_smoke.py" \
        --source-root "$project_root" --wheel "$wheel"
    )
    ;;
  *)
    echo "ASKLENS_TUTORIAL_SMOKE must be 0 or 1." >&2
    exit 2
    ;;
esac

# The article reuses the same installed consumer, isolation and network guards.
# Like the tutorial, it is current-candidate evidence, never a historical probe.
case "${ASKLENS_ARTICLE_SMOKE:-0}" in
  0) ;;
  1)
    if [[ "$mode" != "core" ]]; then
      echo "The integration article requires a core-only wheel environment." >&2
      exit 2
    fi
    (
      cd "$smoke_venv"
      env -u PYTHONPATH -u PYTHONHOME -u DJANGO_SETTINGS_MODULE \
        "$smoke_venv/bin/python" -s \
        "$project_root/.github/scripts/quickstart_smoke.py" \
        --source-root "$project_root" --wheel "$wheel" --article
    )
    ;;
  *)
    echo "ASKLENS_ARTICLE_SMOKE must be 0 or 1." >&2
    exit 2
    ;;
esac

# Current source additions only: never replay new recipes against historical
# published artifacts/upgrade origins unless explicitly requested.
case "${ASKLENS_ADAPTER_SMOKE:-0}" in
  0) ;;
  1)
    (
      cd "$smoke_venv"
      env -u PYTHONPATH -u PYTHONHOME -u DJANGO_SETTINGS_MODULE \
        "$smoke_venv/bin/python" -s \
        "$project_root/.github/scripts/quickstart_smoke.py" \
        --source-root "$project_root" --wheel "$wheel" --adapter "$mode"
    )
    ;;
  *)
    echo "ASKLENS_ADAPTER_SMOKE must be 0 or 1." >&2
    exit 2
    ;;
esac

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
