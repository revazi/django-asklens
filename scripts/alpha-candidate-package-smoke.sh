#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/alpha-candidate-package-smoke.sh [--help]

Build the exact committed 0.3.1 release source into a temporary wheel and source
distribution, exercise isolated core/API/MCP installs, and upgrade authenticated
public PyPI 0.3.0 and 0.2.0 installations while preserving synthetic SQLite
migration state and data. Public 0.3.0 is the immediate maintenance origin;
0.2.0 remains a separate older supported-origin assertion. This produces local
candidate evidence only; it does not support upgrades from 0.1.0a1 or upload,
tag, publish, or release anything.
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
  .github/release-notes .github/scripts \
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
[[ "$(basename "$wheel")" == "django_asklens-0.3.1-py3-none-any.whl" ]] || {
  echo "Unexpected wheel filename: $(basename "$wheel")" >&2
  exit 1
}
[[ "$(basename "$sdist")" == "django_asklens-0.3.1.tar.gz" ]] || {
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
    wheel_names = set(archive.namelist())
    metadata_names = [
        name for name in wheel_names if name.endswith(".dist-info/METADATA")
    ]
    if len(metadata_names) != 1:
        raise SystemExit("Expected one wheel METADATA file.")
    metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
    if metadata["Name"] != "django-asklens" or metadata["Version"] != "0.3.1":
        raise SystemExit("Wheel metadata must identify django-asklens 0.3.1.")
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
packaged_release_notes = sorted(
    name for name in source_names if "/.github/release-notes/" in name
)
if packaged_release_notes:
    raise SystemExit(
        f"Release-review notes leaked into source distribution: {packaged_release_notes}"
    )
if any(".github/release-notes/" in name for name in wheel_names):
    raise SystemExit("Release-review notes leaked into wheel.")
print(
    "PASS source wheel runtime metadata excludes coverage, Docker, httpx, "
    "jsonschema, Playwright, and psycopg"
)
print("PASS source wheel query schema enforces containment value constraints")
print("PASS source distribution contains the documented opt-in evidence artifacts")
print("PASS release-review notes are excluded from package artifacts")
print("PASS wheel metadata identifies django-asklens 0.3.1")
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
  PATH="$(dirname "$evidence_python"):$PATH" \
    ASKLENS_EXPECTED_VERSION=0.3.1 bash .github/scripts/wheel-smoke.sh \
    "$mode" \
    "Django>=6.1,<6.2" \
    "6.1." \
    "$wheel"
  echo "PASS isolated $mode source-wheel install"
done

# Authenticate both supported published origins against immutable, independently
# recorded hashes. Public 0.3.0 is the immediate maintenance origin. Public
# 0.2.0 remains a separate older 0.2.x compatibility assertion.
public_030_dir="$workdir/public-0.3.0"
public_020_dir="$workdir/public-0.2.0"
mkdir "$public_030_dir" "$public_020_dir"
env -u PYTHONPATH "$evidence_python" \
  "$source_tree/scripts/download_pypi_artifacts.py" \
  --version 0.3.0 \
  --wheel-sha256 d7f7159cfdbb3d9755d9b3542f9cda4280f0e72939f81aca4d3a2cd8d8921e8b \
  --sdist-sha256 a7717736c07b93d66e1326dc43a438aa0918c17b4512ddb2391257de5887c5c9 \
  --output-dir "$public_030_dir"
env -u PYTHONPATH "$evidence_python" \
  "$source_tree/scripts/download_pypi_artifacts.py" \
  --version 0.2.0 \
  --wheel-sha256 af0881945d5f5f227332aac8bb13df10d4cf5bd3e54a038acd6545db5640d1d8 \
  --sdist-sha256 11af90303fd2d23123e4caa98c6e6cb660b7b8f32d6fba0c57a4554c8d39e022 \
  --output-dir "$public_020_dir"

run_upgrade_probe() {
  local origin_version="$1"
  local origin_wheel="$2"
  local upgrade_venv="$workdir/upgrade-$origin_version"
  local probe_root="$workdir/migration-probe-$origin_version"
  local probe_project="$probe_root/probeproj"
  local probe_db="$probe_root/probe.sqlite3"
  local probe_secret="asklens-candidate-synthetic-probe-secret"

  uv run --no-sync python -m venv "$upgrade_venv"
  "$upgrade_venv/bin/python" -m pip install --upgrade pip >/dev/null
  "$upgrade_venv/bin/python" -m pip install \
    "Django>=6.1,<6.2" "$origin_wheel" >/dev/null
  (
    cd "$workdir"
    env -u PYTHONPATH \
      ASKLENS_FORBIDDEN_SOURCE_ROOT="$root" \
      ASKLENS_ORIGIN_VERSION="$origin_version" \
      "$upgrade_venv/bin/python" - "$origin_wheel" <<'PY'
from importlib.metadata import version
from pathlib import Path
import os
import sys
import zipfile

import django_asklens

expected = os.environ["ASKLENS_ORIGIN_VERSION"]
public_wheel = Path(sys.argv[1]).resolve()
assert version("django-asklens") == expected
assert django_asklens.__version__ == expected
module_path = Path(django_asklens.__file__).resolve()
assert module_path.is_relative_to(Path(sys.prefix).resolve()), module_path
assert not module_path.is_relative_to(
    Path(os.environ["ASKLENS_FORBIDDEN_SOURCE_ROOT"]).resolve()
), module_path
with zipfile.ZipFile(public_wheel) as archive:
    assert module_path.read_bytes() == archive.read("django_asklens/__init__.py")
print(
    f"PASS authenticated public PyPI django-asklens {expected} installed "
    "without source shadowing"
)
PY
  )

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

  probe_python() {
    (
      cd "$workdir"
      export PYTHONPATH="$probe_root"
      export DJANGO_SETTINGS_MODULE=probeproj.settings
      export ASKLENS_MIGRATION_PROBE_DB="$probe_db"
      export ASKLENS_MIGRATION_PROBE_SECRET="$probe_secret"
      export ASKLENS_ORIGIN_VERSION="$origin_version"
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
import os
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
assert asklens_migrations == {
    ("asklens", "0001_initial"),
    ("asklens", "0002_add_admin_query_proxy"),
}
print("PASS release migration graph is exact: 0001_initial and 0002_add_admin_query_proxy")

origin = os.environ["ASKLENS_ORIGIN_VERSION"]
row = SemanticQueryRun.objects.create(
    question=f"synthetic release probe from {origin}",
    plan={"resource": "synthetic_probe", "intent": "list"},
    status="success",
    row_count=1,
    duration_ms=7,
    error="",
)
assert row.pk == 1
assert SemanticQueryRun.objects.count() == 1
print(f"PASS published {origin} migration state initialized with one synthetic row")
PY

  "$upgrade_venv/bin/python" -m pip install --upgrade "$wheel" >/dev/null
  (
    cd "$workdir"
    env -u PYTHONPATH \
      ASKLENS_FORBIDDEN_SOURCE_ROOT="$root" \
      "$upgrade_venv/bin/python" - "$wheel" "$origin_version" <<'PY'
from importlib.metadata import version
from pathlib import Path
import os
import sys
import zipfile

import django_asklens

wheel = Path(sys.argv[1]).resolve()
origin = sys.argv[2]
assert version("django-asklens") == "0.3.1"
assert django_asklens.__version__ == "0.3.1"
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
print(
    f"PASS local 0.3.1 wheel upgraded authenticated public PyPI {origin} "
    "without source shadowing"
)
PY
  )

  probe_plan_output="$(probe_manage migrate --plan 2>&1)"
  printf 'PASS migrate --plan after public %s to local 0.3.1 upgrade:\n%s\n' \
    "$origin_version" "$probe_plan_output"
  probe_manage migrate --noinput --verbosity 1
  probe_manage showmigrations asklens
  probe_manage check
  probe_manage makemigrations asklens --check --dry-run

  probe_python - <<'PY'
import os
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
assert asklens_migrations == {
    ("asklens", "0001_initial"),
    ("asklens", "0002_add_admin_query_proxy"),
}

executor = MigrationExecutor(connection)
plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
assert not plan

asklens_tables = [
    name
    for name in connection.introspection.table_names()
    if name.startswith("asklens_")
]
assert asklens_tables == ["asklens_semanticqueryrun"]

origin = os.environ["ASKLENS_ORIGIN_VERSION"]
row = SemanticQueryRun.objects.get()
assert row.question == f"synthetic release probe from {origin}"
assert row.plan == {"resource": "synthetic_probe", "intent": "list"}
assert row.status == "success"
assert row.row_count == 1
assert row.duration_ms == 7
assert AskLensQuery._meta.proxy
assert AskLensQuery._meta.db_table == SemanticQueryRun._meta.db_table
assert AskLensQuery.objects.count() == 1
print("PASS release migration graph is exact: 0001_initial and 0002_add_admin_query_proxy")
print(f"PASS synthetic SemanticQueryRun row preserved across {origin} to 0.3.1 upgrade")
print("PASS AskLensQuery remains a proxy over asklens_semanticqueryrun table")
PY

  (
    cd "$workdir"
    env -u PYTHONPATH \
      ASKLENS_EXPECTED_VERSION=0.3.1 \
      ASKLENS_FORBIDDEN_SOURCE_ROOT="$root" \
      DJANGO_VERSION_PREFIX="6.1." \
      "$upgrade_venv/bin/python" "$root/.github/scripts/wheel_smoke.py" core
  )
}

run_upgrade_probe \
  0.3.0 "$public_030_dir/django_asklens-0.3.0-py3-none-any.whl"
run_upgrade_probe \
  0.2.0 "$public_020_dir/django_asklens-0.2.0-py3-none-any.whl"

echo "PASS exact local 0.3.1 candidate, authenticated public 0.3.0 immediate-upgrade evidence, and separate authenticated public 0.2.0 compatibility evidence only; no publication was performed"
