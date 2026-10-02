#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/alpha-candidate-package-smoke.sh [--help]

Build the exact committed 0.3.0 release source into a temporary wheel and source
distribution, exercise isolated core/API/MCP installs, and upgrade an actual
PyPI 0.2.0 installation while preserving SQLite migration state. This produces
local package evidence only; it does not support upgrades from 0.1.0a1 or
upload, tag, publish, or release anything.
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
command -v git >/dev/null 2>&1 || {
  echo "git is required to identify and export the exact source commit." >&2
  exit 1
}
command -v tar >/dev/null 2>&1 || {
  echo "tar is required to unpack the exact source commit." >&2
  exit 1
}

source_status="$(git status --porcelain --untracked-files=all)"
if [[ -n "$source_status" ]]; then
  echo "Refusing to build package evidence from a dirty source tree:" >&2
  printf '%s\n' "$source_status" >&2
  exit 1
fi
source_commit="$(git rev-parse --verify HEAD)"

workdir="$(mktemp -d)"
cleanup() {
  rm -r "$workdir"
}
trap cleanup EXIT
artifacts="$workdir/artifacts"
source_tree="$workdir/source"
mkdir -p "$artifacts" "$source_tree"
git archive "$source_commit" -- \
  .github/scripts/wheel-smoke.sh .github/scripts/wheel_smoke.py \
  CHANGELOG.md CONTRIBUTING.md LICENSE MANIFEST.in README.md SECURITY.md \
  compose.yaml pyproject.toml conformance django_asklens docs examples scripts \
  tests/e2e \
  | tar -x -C "$source_tree"
echo "Building exact source commit: $source_commit"
evidence_python="$(uv run --no-sync python -c 'import sys; print(sys.executable)')"

build_log="$workdir/build.log"
if ! (cd "$source_tree" && "$evidence_python" -m build --outdir "$artifacts") \
  >"$build_log"; then
  cat "$build_log" >&2
  exit 1
fi
shopt -s nullglob
wheels=("$artifacts"/django_asklens-*.whl)
sdists=("$artifacts"/django_asklens-*.tar.gz)
shopt -u nullglob
if [[ ${#wheels[@]} -ne 1 || ${#sdists[@]} -ne 1 ]]; then
  echo "Expected exactly one wheel and one source distribution." >&2
  exit 1
fi
wheel="${wheels[0]}"
sdist="${sdists[0]}"
[[ "$(basename "$wheel")" == "django_asklens-0.3.0-py3-none-any.whl" ]] || {
  echo "Unexpected wheel filename: $(basename "$wheel")" >&2
  exit 1
}
[[ "$(basename "$sdist")" == "django_asklens-0.3.0.tar.gz" ]] || {
  echo "Unexpected source distribution filename: $(basename "$sdist")" >&2
  exit 1
}
uv run --no-sync twine check "$wheel" "$sdist"

uv run --no-sync python - "$wheel" "$sdist" <<'PY'
from email.parser import Parser
from pathlib import Path
import json
import re
import sys
import tarfile
import zipfile

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError

wheel = Path(sys.argv[1])
sdist = Path(sys.argv[2])
with zipfile.ZipFile(wheel) as archive:
    metadata_names = [
        name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
    ]
    if len(metadata_names) != 1:
        raise SystemExit("Expected one wheel METADATA file.")
    metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
    if metadata["Name"] != "django-asklens" or metadata["Version"] != "0.3.0":
        raise SystemExit("Wheel metadata must identify django-asklens 0.3.0.")
    query_schema = json.loads(
        archive.read(
            "django_asklens/contracts/schemas/query-plan.schema.json"
        ).decode("utf-8")
    )

Draft202012Validator.check_schema(query_schema)
query_validator = Draft202012Validator(query_schema)
for operator in ("contains", "icontains"):
    valid_plan = {
        "resource": "orders",
        "intent": "list",
        "filters": [{"field": "status", "op": operator, "value": "paid"}],
    }
    query_validator.validate(valid_plan)
    for value in ("", 1, True):
        invalid_plan = {
            **valid_plan,
            "filters": [{"field": "status", "op": operator, "value": value}],
        }
        try:
            query_validator.validate(invalid_plan)
        except SchemaValidationError:
            pass
        else:
            raise SystemExit(
                f"Packaged query schema accepted invalid {operator} value {value!r}."
            )

forbidden_prefixes = (
    "coverage",
    "docker",
    "httpx",
    "jsonschema",
    "playwright",
    "psycopg",
)
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
    "/.github/scripts/wheel-smoke.sh",
    "/.github/scripts/wheel_smoke.py",
    "/compose.yaml",
    "/docs/test-coverage.md",
    "/scripts/alpha-candidate-package-smoke.sh",
    "/scripts/coverage-baseline.sh",
    "/scripts/download_pypi_artifacts.py",
    "/scripts/published-package-smoke.sh",
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
print(
    "PASS source wheel runtime metadata excludes coverage, Docker, httpx, "
    "jsonschema, Playwright, and psycopg"
)
print("PASS source wheel query schema enforces containment value constraints")
print("PASS source distribution contains the documented opt-in evidence artifacts")
print("PASS wheel metadata identifies django-asklens 0.3.0")
PY

uv run --no-sync python - "$wheel" "$sdist" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

for artifact_name in sys.argv[1:]:
    artifact = Path(artifact_name)
    print(f"ARTIFACT_SHA256 {artifact.name} {sha256(artifact.read_bytes()).hexdigest()}")
PY

# Reuse the installed-wheel checks used by CI, once per supported package surface.
for mode in core api mcp; do
  bash .github/scripts/wheel-smoke.sh \
    "$mode" \
    "Django>=6.1,<6.2" \
    "6.1." \
    "$wheel"
  echo "PASS isolated $mode source-wheel install"
done

upgrade_venv="$workdir/upgrade"
uv run --no-sync python -m venv "$upgrade_venv"
"$upgrade_venv/bin/python" -m pip install --upgrade pip >/dev/null
"$upgrade_venv/bin/python" -m pip install \
  --index-url https://pypi.org/simple \
  "Django>=5.2,<7.0" \
  "django-asklens==0.2.0" >/dev/null
(
  cd "$workdir"
  env -u PYTHONPATH \
    ASKLENS_FORBIDDEN_SOURCE_ROOT="$root" \
    "$upgrade_venv/bin/python" - <<'PY'
from importlib.metadata import version
from pathlib import Path
import os
import sys

import django_asklens

assert version("django-asklens") == "0.2.0"
assert django_asklens.__version__ == "0.2.0"
module_path = Path(django_asklens.__file__).resolve()
assert module_path.is_relative_to(Path(sys.prefix).resolve()), module_path
assert not module_path.is_relative_to(
    Path(os.environ["ASKLENS_FORBIDDEN_SOURCE_ROOT"]).resolve()
), module_path
print("PASS actual PyPI django-asklens 0.2.0 installed without source shadowing")
PY
)

# Supported 0.2.0 -> 0.3.0 migration-state preservation is synthetic SQLite
# evidence only. The 0.1.0a1 testing artifact is not an upgrade origin.
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
"""Probe settings used to exercise release migration state in SQLite."""

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
    cd "$workdir"
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
print("PASS release migration graph is exact: 0001_initial and 0002_add_admin_query_proxy")

row = SemanticQueryRun.objects.create(
    question="synthetic release probe",
    plan={"resource": "synthetic_probe", "intent": "list"},
    status="success",
    row_count=1,
    duration_ms=7,
    error="",
)
assert row.pk == 1
assert SemanticQueryRun.objects.count() == 1
print("PASS published 0.2.0 migration state initialized with one synthetic row")
PY

"$upgrade_venv/bin/python" -m pip install --upgrade "$wheel" >/dev/null
(
  cd "$workdir"
  env -u PYTHONPATH \
    ASKLENS_FORBIDDEN_SOURCE_ROOT="$root" \
    "$upgrade_venv/bin/python" - "$wheel" <<'PY'
from importlib.metadata import version
from pathlib import Path
import os
import sys
import zipfile

import django_asklens

wheel = Path(sys.argv[1]).resolve()
assert version("django-asklens") == "0.3.0"
assert django_asklens.__version__ == "0.3.0"
module_path = Path(django_asklens.__file__).resolve()
assert module_path.is_relative_to(Path(sys.prefix).resolve()), module_path
assert not module_path.is_relative_to(
    Path(os.environ["ASKLENS_FORBIDDEN_SOURCE_ROOT"]).resolve()
), module_path
critical_files = (
    "__init__.py",
    "execution/runner.py",
    "observability.py",
    "contracts/schemas/capabilities.schema.json",
)
with zipfile.ZipFile(wheel) as archive:
    for relative_path in critical_files:
        assert (module_path.parent / relative_path).read_bytes() == archive.read(
            f"django_asklens/{relative_path}"
        )
print("PASS local 0.3.0 wheel upgraded PyPI 0.2.0 without source shadowing")
PY
)

probe_plan_output="$(probe_manage migrate --plan 2>&1)"
printf 'PASS migrate --plan after 0.2.0 to local 0.3.0 upgrade:\n%s\n' "$probe_plan_output"
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
assert row.question == "synthetic release probe"
assert row.plan == {"resource": "synthetic_probe", "intent": "list"}
assert row.status == "success"
assert row.row_count == 1
assert row.duration_ms == 7
assert AskLensQuery._meta.proxy
assert AskLensQuery._meta.db_table == SemanticQueryRun._meta.db_table
assert AskLensQuery.objects.count() == 1
print("PASS release migration graph is exact: 0001_initial and 0002_add_admin_query_proxy")
print("PASS synthetic SemanticQueryRun row preserved across 0.2.0 to 0.3.0 upgrade")
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
assert version("django-asklens") == "0.3.0"
assert django_asklens.__version__ == "0.3.0"
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
print("PASS exact local 0.3.0 install matches source-wheel files")
PY
)
(
  cd "$workdir"
  DJANGO_VERSION_PREFIX="6.1." \
    "$upgrade_venv/bin/python" "$root/.github/scripts/wheel_smoke.py" core
)

echo "PASS exact local 0.3.0 and PyPI 0.2.0 upgrade evidence only; no publication was performed"
