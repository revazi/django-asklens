#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/published-package-smoke.sh \
  --version VERSION \
  --wheel-sha256 HEX \
  --sdist-sha256 HEX \
  [--django-package SPEC] \
  [--django-version-prefix PREFIX]

Download the exact wheel and source distribution from PyPI's fixed project
endpoint, authenticate both with independently supplied SHA-256 values, and
exercise isolated core/API/MCP installs plus Django migration checks.

The script never uploads, publishes, tags, or changes remote configuration.
EOF
}

version=""
wheel_sha256=""
sdist_sha256=""
django_package="Django>=6.1,<6.2"
django_version_prefix="6.1."
while (($#)); do
  case "$1" in
    --version)
      version="${2:?Missing --version value}"
      shift 2
      ;;
    --wheel-sha256)
      wheel_sha256="${2:?Missing --wheel-sha256 value}"
      shift 2
      ;;
    --sdist-sha256)
      sdist_sha256="${2:?Missing --sdist-sha256 value}"
      shift 2
      ;;
    --django-package)
      django_package="${2:?Missing --django-package value}"
      shift 2
      ;;
    --django-version-prefix)
      django_version_prefix="${2:?Missing --django-version-prefix value}"
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

if [[ -z "$version" || -z "$wheel_sha256" || -z "$sdist_sha256" ]]; then
  echo "--version, --wheel-sha256, and --sdist-sha256 are required." >&2
  usage >&2
  exit 2
fi
if ! [[ "$version" =~ ^[0-9][A-Za-z0-9.!+_-]*$ ]]; then
  echo "Invalid release version." >&2
  exit 2
fi
if ! [[ "$wheel_sha256" =~ ^[0-9a-f]{64}$ && "$sdist_sha256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Artifact digests must be lowercase SHA-256 values." >&2
  exit 2
fi
if ! [[ "$django_version_prefix" =~ ^[0-9]+\.[0-9]+\.$ ]]; then
  echo "Django version prefix must look like 6.1." >&2
  exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v python >/dev/null 2>&1 || {
  echo "Python 3.12 or newer is required." >&2
  exit 1
}
python -c 'import sys; assert sys.version_info >= (3, 12)' || {
  echo "Python 3.12 or newer is required." >&2
  exit 1
}

workdir="$(mktemp -d)"
cleanup() {
  rm -rf "$workdir"
}
trap cleanup EXIT
artifacts="$workdir/artifacts"
mkdir "$artifacts"

(
  cd "$workdir"
  env -u PYTHONPATH python "$root/scripts/download_pypi_artifacts.py" \
    --version "$version" \
    --wheel-sha256 "$wheel_sha256" \
    --sdist-sha256 "$sdist_sha256" \
    --output-dir "$artifacts"
)

wheel="$artifacts/django_asklens-${version}-py3-none-any.whl"
sdist="$artifacts/django_asklens-${version}.tar.gz"
[[ -f "$wheel" && -f "$sdist" ]] || {
  echo "Authenticated release artifacts were not downloaded as expected." >&2
  exit 1
}

# Each artifact and optional surface gets a new virtual environment. The shared
# probe runs from that environment's temporary directory with PYTHONPATH unset.
export ASKLENS_EXPECTED_VERSION="$version"
for artifact in "$wheel" "$sdist"; do
  for mode in core api mcp; do
    bash "$root/.github/scripts/wheel-smoke.sh" \
      "$mode" "$django_package" "$django_version_prefix" "$artifact"
    echo "PASS isolated published $(basename "$artifact") $mode install"
  done
done

migration_venv="$workdir/migration-venv"
python -m venv "$migration_venv"
"$migration_venv/bin/python" -m pip install --quiet --upgrade pip
"$migration_venv/bin/python" -m pip install --quiet "$django_package" "$wheel"
probe_root="$workdir/migration-probe"
mkdir -p "$probe_root/probeproj"
cat > "$probe_root/probeproj/__init__.py" <<'PY'
"""Disposable package used by the published-artifact migration probe."""
PY
cat > "$probe_root/probeproj/urls.py" <<'PY'
urlpatterns = []
PY
cat > "$probe_root/probeproj/settings.py" <<'PY'
"""Settings for a synthetic SQLite published-artifact probe."""

import os

SECRET_KEY = "synthetic-published-artifact-probe"
DEBUG = False
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django_asklens",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ["ASKLENS_PUBLISHED_PROBE_DB"],
    }
}
MIDDLEWARE = []
ROOT_URLCONF = "probeproj.urls"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
PY

probe_manage() {
  (
    cd "$workdir"
    export PYTHONPATH="$probe_root"
    export DJANGO_SETTINGS_MODULE=probeproj.settings
    export ASKLENS_PUBLISHED_PROBE_DB="$workdir/probe.sqlite3"
    "$migration_venv/bin/python" -m django "$@"
  )
}

probe_manage check
probe_manage migrate --plan
probe_manage migrate --noinput --verbosity 0
probe_manage showmigrations asklens
probe_manage migrate --plan
probe_manage makemigrations asklens --check --dry-run
(
  cd "$workdir"
  env -u PYTHONPATH \
    ASKLENS_EXPECTED_VERSION="$version" \
    ASKLENS_FORBIDDEN_SOURCE_ROOT="$root" \
    "$migration_venv/bin/python" - <<'PY'
from importlib.metadata import version
from pathlib import Path
import os

import django_asklens

expected = os.environ["ASKLENS_EXPECTED_VERSION"]
assert version("django-asklens") == expected
assert django_asklens.__version__ == expected
source_root = Path(os.environ["ASKLENS_FORBIDDEN_SOURCE_ROOT"]).resolve()
module_path = Path(django_asklens.__file__).resolve()
assert not module_path.is_relative_to(source_root), module_path
print(f"PASS published migration probe imported isolated {module_path}")
PY
)

echo "PASS published django-asklens==$version wheel and sdist verification"
