#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/alpha-candidate-package-smoke.sh [--help]

Build the unchanged source version into a temporary wheel, exercise isolated
core/API/MCP installs, and replace the published 0.1.0a1 install with that local
wheel. This produces alpha-candidate proposal evidence only; it does not bump a
version, upload, tag, publish, or release anything. Network access to PyPI is
required for the published-version and dependency installs.
EOF
}

case "${1:-}" in
  "") ;;
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
cd "$root"
command -v uv >/dev/null 2>&1 || {
  echo "uv is required. See docs/installation.md." >&2
  exit 1
}

workdir="$(mktemp -d)"
cleanup() {
  rm -r "$workdir"
}
trap cleanup EXIT
artifacts="$workdir/artifacts"
source_tree="$workdir/source"
mkdir -p "$artifacts" "$source_tree"
for source_file in \
  CHANGELOG.md CONTRIBUTING.md LICENSE MANIFEST.in README.md SECURITY.md compose.yaml pyproject.toml; do
  cp "$source_file" "$source_tree/"
done
for source_directory in conformance django_asklens docs examples scripts; do
  cp -R "$source_directory" "$source_tree/"
done
mkdir -p "$source_tree/tests"
cp -R tests/e2e "$source_tree/tests/"
evidence_python="$(uv run --no-sync python -c 'import sys; print(sys.executable)')"

build_log="$workdir/build.log"
if ! (cd "$source_tree" && "$evidence_python" -m build --outdir "$artifacts") \
  >"$build_log"; then
  cat "$build_log" >&2
  exit 1
fi
wheel="$(find "$artifacts" -maxdepth 1 -type f -name 'django_asklens-*.whl')"
sdist="$(find "$artifacts" -maxdepth 1 -type f -name 'django_asklens-*.tar.gz')"
[[ -f "$wheel" && -f "$sdist" ]] || {
  echo "Expected exactly one source wheel and source distribution." >&2
  exit 1
}

uv run --no-sync python - "$wheel" "$sdist" <<'PY'
from email.parser import Parser
from pathlib import Path
import re
import sys
import tarfile
import zipfile

wheel = Path(sys.argv[1])
sdist = Path(sys.argv[2])
with zipfile.ZipFile(wheel) as archive:
    metadata_names = [
        name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
    ]
    if len(metadata_names) != 1:
        raise SystemExit("Expected one wheel METADATA file.")
    metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))

forbidden_prefixes = ("docker", "playwright", "psycopg")
requirements = metadata.get_all("Requires-Dist", [])
requirement_names = {
    re.split(r"[ (;<>=!~]", requirement.lower().replace("_", "-"), maxsplit=1)[0]
    for requirement in requirements
}
leaked = sorted(
    name for name in requirement_names if name.startswith(forbidden_prefixes)
)
if leaked:
    raise SystemExit(f"Development-only dependencies leaked into wheel metadata: {leaked}")
if "dev" in (metadata.get_all("Provides-Extra", []) or []):
    raise SystemExit("The development group leaked into wheel extras.")

with tarfile.open(sdist, "r:gz") as archive:
    source_names = set(archive.getnames())
required_source_suffixes = {
    "/compose.yaml",
    "/scripts/alpha-candidate-package-smoke.sh",
    "/scripts/reference-demo-smoke.sh",
    "/tests/e2e/reference_demo.py",
}
missing_source = sorted(
    suffix
    for suffix in required_source_suffixes
    if not any(name.endswith(suffix) for name in source_names)
)
if missing_source:
    raise SystemExit(f"Source distribution omitted reference evidence: {missing_source}")
print("PASS source wheel runtime metadata excludes Docker, Playwright, and psycopg")
print("PASS source distribution contains the documented opt-in evidence artifacts")
PY

# Reuse the installed-wheel checks used by CI, once per supported package surface.
for mode in core api mcp; do
  bash .github/scripts/wheel-smoke.sh \
    "$mode" \
    "Django>=6.0,<7.0" \
    "6." \
    "$wheel"
  echo "PASS isolated $mode source-wheel install"
done

upgrade_venv="$workdir/upgrade"
uv run --no-sync python -m venv "$upgrade_venv"
"$upgrade_venv/bin/python" -m pip install --upgrade pip >/dev/null
"$upgrade_venv/bin/python" -m pip install \
  --index-url https://pypi.org/simple \
  "django-asklens==0.1.0a1" >/dev/null
"$upgrade_venv/bin/python" - <<'PY'
from importlib.metadata import version

assert version("django-asklens") == "0.1.0a1"
print("PASS published 0.1.0a1 installed from PyPI")
PY

# The repository version intentionally remains 0.1.0a1 until a separate release.
# Force replacement is therefore required to exercise the local wheel now;
# an authorized 0.2.0a* version bump must rerun this as a normal resolver upgrade.
probe_root="$workdir/migration-probe"
probe_project="$probe_root/probeproj"
probe_db="$probe_root/probe.sqlite3"
probe_secret="asklens-pr10-probe-secret"
mkdir -p "$probe_project"
cat > "$probe_project/__init__.py" <<'EOF'
"""Disposable probe project package for package evidence."""
EOF
cat > "$probe_project/urls.py" <<'EOF'
urlpatterns = []
EOF
cat > "$probe_project/settings.py" <<'EOF'
"""Probe settings used to exercise published/local migration state in SQLite."""

import os

SECRET_KEY = os.environ["ASKLENS_MIGRATION_PROBE_SECRET"]
DEBUG = False

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django_asklens",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ["ASKLENS_MIGRATION_PROBE_DB"],
    }
}

MIDDLEWARE = []
ROOT_URLCONF = "probeproj.urls"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
EOF

# SQLite-only migration-state preservation; this is package evidence, not a production upgrade check.
probe_python() {
  (
    export PYTHONPATH="$probe_root"
    export DJANGO_SETTINGS_MODULE=probeproj.settings
    export ASKLENS_MIGRATION_PROBE_DB="$probe_db"
    export ASKLENS_MIGRATION_PROBE_SECRET="$probe_secret"
    "$upgrade_venv/bin/python" "$@"
  )
}

probe_manage() {
  local manage_command="$1"
  shift
  probe_python -m django "$manage_command" "$@"
}

probe_manage migrate --noinput --verbosity 1
probe_python - <<'PY'
import django

django.setup()

from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django_asklens.models import SemanticQueryRun

asklens_migrations = {
    migration
    for migration in MigrationRecorder(connection).applied_migrations()
    if migration[0] == "asklens"
}
assert asklens_migrations == {("asklens", "0001_initial"), ("asklens", "0002_add_admin_query_proxy")}
print("PASS published migration graph is exact: 0001_initial and 0002_add_admin_query_proxy")

row = SemanticQueryRun.objects.create(
    question="synthetic published probe",
    plan={"resource": "synthetic_probe", "intent": "list"},
    status="success",
    row_count=1,
    duration_ms=7,
    error="",
)
assert row.pk == 1
assert SemanticQueryRun.objects.count() == 1
print("PASS published 0.1.0a1 migration path initialized with one synthetic row")
PY

"$upgrade_venv/bin/python" -m pip install \
  --force-reinstall --no-deps "$wheel" >/dev/null
probe_plan_output="$(probe_manage migrate --plan 2>&1)"
printf 'PASS migrate --plan after local same-version replacement:\n%s\n' "$probe_plan_output"
probe_manage migrate --noinput --verbosity 1
probe_manage showmigrations asklens
probe_manage check
probe_manage makemigrations asklens --check --dry-run

probe_python - <<'PY'
import django

django.setup()

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django_asklens.models import AskLensQuery, SemanticQueryRun

asklens_migrations = {
    migration
    for migration in MigrationRecorder(connection).applied_migrations()
    if migration[0] == "asklens"
}
assert asklens_migrations == {("asklens", "0001_initial"), ("asklens", "0002_add_admin_query_proxy")}

executor = MigrationExecutor(connection)
plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
assert not plan

asklens_tables = [
    name
    for name in connection.introspection.table_names()
    if name.startswith("asklens_")
]
assert asklens_tables == ["asklens_semanticqueryrun"]

row = SemanticQueryRun.objects.get()
assert row.question == "synthetic published probe"
assert row.plan == {"resource": "synthetic_probe", "intent": "list"}
assert row.status == "success"
assert row.row_count == 1
assert row.duration_ms == 7
assert AskLensQuery._meta.proxy
assert AskLensQuery._meta.db_table == SemanticQueryRun._meta.db_table
assert AskLensQuery.objects.count() == 1
print("PASS migration graph after local same-version replacement is exact: 0001_initial and 0002_add_admin_query_proxy")
print("PASS synthetic SemanticQueryRun row preserved across same-version replacement")
print("PASS AskLensQuery remains a proxy over asklens_semanticqueryrun table")
PY

(
  cd "$workdir"
  "$upgrade_venv/bin/python" - "$wheel" <<'PY'
from importlib.metadata import version
from pathlib import Path
import sys
import zipfile

import django_asklens

wheel = Path(sys.argv[1]).resolve()
assert version("django-asklens") == "0.1.0a1"
assert django_asklens.__version__ == "0.1.0a1"
assert callable(django_asklens.list_contract_schemas)
installed_root = Path(django_asklens.__file__).resolve().parent
critical_files = (
    "__init__.py",
    "execution/runner.py",
    "contracts/schemas/capabilities.schema.json",
)
with zipfile.ZipFile(wheel) as archive:
    for relative_path in critical_files:
        assert (installed_root / relative_path).read_bytes() == archive.read(
            f"django_asklens/{relative_path}"
        )
print("PASS published install replaced by exact local source-wheel files")
PY
)
DJANGO_VERSION_PREFIX="6." \
  "$upgrade_venv/bin/python" .github/scripts/wheel_smoke.py core

echo "PASS package evidence only; no version change or release was performed"
