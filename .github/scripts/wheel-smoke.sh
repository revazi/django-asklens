#!/usr/bin/env bash
set -euo pipefail

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
python -m venv "$smoke_venv"
wheel="$(echo dist/django_asklens-*.whl)"
"$smoke_venv/bin/python" -m pip install --upgrade pip
"$smoke_venv/bin/python" -m pip install "$django_package"
"$smoke_venv/bin/python" -m pip install "${wheel}${extra}"
DJANGO_VERSION_PREFIX="$django_version_prefix" "$smoke_venv/bin/python" .github/scripts/wheel_smoke.py "$mode"
