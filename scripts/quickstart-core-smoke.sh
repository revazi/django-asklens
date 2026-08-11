#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/quickstart-core-smoke.sh [--help]

Build one wheel from the current tracked local source files, install that exact
wheel with core dependencies only, create a disposable synthetic Django project,
and exercise the documented trusted core quickstart. Normal package build and
dependency installation may use the configured package indexes. No provider,
container, DRF, frontend, or MCP call is made.
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
command -v git >/dev/null 2>&1 || {
  echo "git is required to select the tracked local source inputs." >&2
  exit 1
}
command -v uv >/dev/null 2>&1 || {
  echo "uv is required to build the local source wheel." >&2
  exit 1
}
command -v python >/dev/null 2>&1 || {
  echo "Python 3.12 or newer is required." >&2
  exit 1
}
python - <<'PY'
import sys

if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12 or newer is required.")
PY

temp_parent="${TMPDIR:-/tmp}"
temp_parent="${temp_parent%/}"
if [[ -z "$temp_parent" ]]; then
  temp_parent="/"
fi
workdir="$(mktemp -d "${temp_parent}/django-asklens-core-quickstart.XXXXXX")"
owned_prefix="${temp_parent}/django-asklens-core-quickstart."

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  case "$workdir" in
    "$owned_prefix"*)
      if [[ -d "$workdir" ]] && ! rm -r -- "$workdir"; then
        echo "cleanup_status=failed" >&2
        exit_code=1
      else
        echo "cleanup_status=complete"
      fi
      ;;
    *)
      echo "cleanup_status=refused_unowned_path" >&2
      exit_code=1
      ;;
  esac
  exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Keep build/install tool temporaries inside the same owned root so the trap
# removes them without touching the caller's TMPDIR.
process_tmp="$workdir/tmp"
source_tree="$workdir/source"
wheel_dir="$workdir/wheel"
venv="$workdir/venv"
project_root="$workdir/project"
mkdir -p "$process_tmp" "$source_tree" "$wheel_dir" "$project_root"
export TMPDIR="$process_tmp"

# Copy current working-tree bytes for tracked wheel inputs only. This excludes
# caller caches and generated artifacts while preserving any deliberate local
# source edit. The source and resulting wheel hashes identify the tested bytes.
while IFS= read -r -d '' relative_path; do
  mkdir -p "$source_tree/$(dirname "$relative_path")"
  cp "$root/$relative_path" "$source_tree/$relative_path"
done < <(
  git -C "$root" ls-files -z -- \
    LICENSE README.md pyproject.toml django_asklens
)
for required_path in pyproject.toml README.md LICENSE django_asklens/__init__.py; do
  [[ -f "$source_tree/$required_path" ]] || {
    echo "Tracked local wheel input is missing: $required_path" >&2
    exit 1
  }
done

source_sha256="$(python - "$source_tree" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

root = Path(sys.argv[1])
digest = sha256()
for path in sorted(item for item in root.rglob("*") if item.is_file()):
    relative = path.relative_to(root).as_posix().encode()
    digest.update(len(relative).to_bytes(8, "big"))
    digest.update(relative)
    content = path.read_bytes()
    digest.update(len(content).to_bytes(8, "big"))
    digest.update(content)
print(digest.hexdigest())
PY
)"

build_log="$workdir/build.log"
if ! uv run --no-sync python -m build --wheel \
  --outdir "$wheel_dir" "$source_tree" >"$build_log" 2>&1; then
  tail -n 80 "$build_log" >&2
  exit 1
fi
wheel_count="$(find "$wheel_dir" -maxdepth 1 -type f -name 'django_asklens-*.whl' | wc -l | tr -d ' ')"
[[ "$wheel_count" == "1" ]] || {
  echo "Expected exactly one locally built django-asklens wheel." >&2
  exit 1
}
wheel="$(find "$wheel_dir" -maxdepth 1 -type f -name 'django_asklens-*.whl')"
wheel_sha256="$(python - "$wheel" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

print(sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"
printf 'source_sha256=%s\nwheel_sha256=%s\n' "$source_sha256" "$wheel_sha256"

python -m venv "$venv"
install_log="$workdir/install.log"
if ! "$venv/bin/python" -m pip install --no-cache-dir "$wheel" \
  >"$install_log" 2>&1; then
  tail -n 80 "$install_log" >&2
  exit 1
fi

# Prove the isolated environment installed the exact wheel path and no optional
# API/MCP package. Compare every packaged AskLens file against the wheel bytes.
"$venv/bin/python" - "$wheel" <<'PY'
from importlib import metadata, util
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse
import zipfile

wheel = Path(sys.argv[1]).resolve()
distribution = metadata.distribution("django-asklens")
direct_url_text = distribution.read_text("direct_url.json")
if direct_url_text is None:
    raise SystemExit("Exact local wheel installation has no direct_url.json.")
direct_url = json.loads(direct_url_text)
parsed = urlparse(direct_url["url"])
installed_from = Path(unquote(parsed.path)).resolve()
if installed_from != wheel:
    raise SystemExit("Isolated install did not use the exact locally built wheel.")
if util.find_spec("rest_framework") is not None:
    raise SystemExit("DRF unexpectedly appeared in the core-only environment.")
if util.find_spec("fastmcp") is not None:
    raise SystemExit("FastMCP unexpectedly appeared in the core-only environment.")

import django_asklens

installed_root = Path(django_asklens.__file__).resolve().parent
with zipfile.ZipFile(wheel) as archive:
    package_files = [
        name
        for name in archive.namelist()
        if name.startswith("django_asklens/") and not name.endswith("/")
    ]
    if not package_files:
        raise SystemExit("The local wheel contains no AskLens package files.")
    for archive_name in package_files:
        relative = archive_name.removeprefix("django_asklens/")
        if (installed_root / relative).read_bytes() != archive.read(archive_name):
            raise SystemExit("Installed AskLens bytes differ from the local wheel.")
print("core_install_status=exact-wheel-core-only")
PY

"$venv/bin/django-admin" startproject quickstart "$project_root"
(
  cd "$project_root"
  "$venv/bin/python" manage.py startapp shop
)

cat >"$project_root/quickstart/settings.py" <<'PY'
"""Disposable core-quickstart settings using synthetic SQLite data."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "synthetic-core-quickstart-only"
DEBUG = False
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django_asklens",
    "shop.apps.ShopConfig",
]

MIDDLEWARE = []
ROOT_URLCONF = "quickstart.urls"
TEMPLATES = []
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DJANGO_ASKLENS = {
    "LLM_BACKEND": "dummy",
    "AUDIT_INCLUDE_CONTENT": False,
}
PY

cat >"$project_root/quickstart/urls.py" <<'PY'
"""No HTTP routes are needed for the core-only smoke."""

urlpatterns = []
PY

cat >"$project_root/shop/models.py" <<'PY'
"""Synthetic host models for the disposable quickstart."""

from django.db import models


class GlobalFact(models.Model):
    """Non-sensitive shared data deliberately reviewed as global."""

    code = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=100)


class ScopedFact(models.Model):
    """Synthetic data restricted by current server-owned request identity."""

    scope_key = models.CharField(max_length=150)
    label = models.CharField(max_length=100)
PY

cat >"$project_root/shop/asklens_registration.py" <<'PY'
"""The one project-owned AskLens registration module."""

from django_asklens import register

from .models import GlobalFact, ScopedFact


def visible_scoped_facts(request):
    """Resolve scope from the current authenticated server-owned request."""

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return ScopedFact.objects.none()
    return ScopedFact.objects.filter(scope_key=user.get_username())


register(
    timezone="UTC",
    model=GlobalFact,
    name="global_facts",
    label="Reviewed global facts",
    description="Synthetic non-sensitive facts reviewed for global row access.",
    fields={
        "code": {
            "binding": "code",
            "type": "string",
            "nullable": False,
            "label": "Code",
        },
        "label": {
            "binding": "label",
            "type": "string",
            "nullable": False,
            "label": "Label",
        },
    },
    default_order=(("code", "asc"),),
    scope_mode="global",
)

register(
    timezone="UTC",
    model=ScopedFact,
    name="scoped_facts",
    label="Scoped facts",
    description="Synthetic facts restricted to the current request scope.",
    fields={
        "label": {
            "binding": "label",
            "type": "string",
            "nullable": False,
            "label": "Label",
        },
    },
    default_order=(("label", "asc"),),
    requires_permission="shop.view_scopedfact",
    scope_mode="context_scoped",
    scope_provider=visible_scoped_facts,
)
PY

cat >"$project_root/shop/apps.py" <<'PY'
"""Project-owned startup wiring for one controlled registration import."""

from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"

    def ready(self):
        """Import registration once; AskLens does not autodiscover it."""

        from . import asklens_registration  # noqa: F401
PY

cat >"$project_root/core_smoke.py" <<'PY'
"""Execute synthetic plans through current server-owned Django requests."""

import hashlib
import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quickstart.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from django_asklens.exceptions import PublicAskLensError
from django_asklens.execution import execute_plan
from shop.models import GlobalFact, ScopedFact


def current_request(factory, user):
    """Return a synthetic current request populated by trusted host code."""

    request = factory.get("/trusted-core-smoke/")
    request.user = user
    return request


def stable_projection(result):
    """Exclude execution timing while retaining canonical result semantics."""

    payload = result.to_dict()
    return {
        "columns": payload["columns"],
        "data": payload["data"],
        "result_metadata": payload["result_metadata"],
    }


def projection_sha256(result):
    """Hash a canonical synthetic projection without printing result rows."""

    encoded = json.dumps(
        stable_projection(result),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


GlobalFact.objects.bulk_create(
    [
        GlobalFact(code="first", label="First reviewed fact"),
        GlobalFact(code="second", label="Second reviewed fact"),
    ]
)
ScopedFact.objects.bulk_create(
    [
        ScopedFact(scope_key="scope-alpha", label="First scoped fact"),
        ScopedFact(scope_key="scope-alpha", label="Second scoped fact"),
        ScopedFact(scope_key="scope-bravo", label="Third scoped fact"),
    ]
)

User = get_user_model()
alpha_user = User.objects.create_user(username="scope-alpha")
bravo_user = User.objects.create_user(username="scope-bravo")
denied_user = User.objects.create_user(username="scope-denied")
view_permission = Permission.objects.get(
    content_type__app_label="shop",
    codename="view_scopedfact",
)
alpha_user.user_permissions.add(view_permission)
bravo_user.user_permissions.add(view_permission)

factory = RequestFactory()
alpha_request = current_request(factory, alpha_user)
bravo_request = current_request(factory, bravo_user)
denied_request = current_request(factory, denied_user)

global_plan = {
    "resource": "global_facts",
    "intent": "list",
    "select": ["code", "label"],
    "limit": 20,
}
scoped_plan = {
    "resource": "scoped_facts",
    "intent": "list",
    "select": ["label"],
    "limit": 20,
}

global_first = execute_plan(global_plan, request=alpha_request)
global_second = execute_plan(global_plan, request=alpha_request)
alpha_first = execute_plan(scoped_plan, request=alpha_request)
alpha_second = execute_plan(scoped_plan, request=alpha_request)
bravo_result = execute_plan(scoped_plan, request=bravo_request)

assert global_first.row_count == 2
assert stable_projection(global_first) == stable_projection(global_second)
assert alpha_first.row_count == 2
assert stable_projection(alpha_first) == stable_projection(alpha_second)
assert bravo_result.row_count == 1
assert {row["label"] for row in alpha_first.rows} == {
    "First scoped fact",
    "Second scoped fact",
}
assert {row["label"] for row in bravo_result.rows} == {"Third scoped fact"}

global_hash = projection_sha256(global_first)
alpha_hash = projection_sha256(alpha_first)
bravo_hash = projection_sha256(bravo_result)
assert alpha_hash != bravo_hash

with CaptureQueriesContext(connection) as captured:
    try:
        execute_plan(scoped_plan, request=denied_request)
    except PublicAskLensError as exc:
        denial_code = exc.code
    else:
        raise AssertionError("The current user without permission was not denied.")

application_tables = (
    GlobalFact._meta.db_table.lower(),
    ScopedFact._meta.db_table.lower(),
)
application_data_queries = sum(
    any(table in query["sql"].lower() for table in application_tables)
    for query in captured.captured_queries
)
assert denial_code == "asklens.member.unavailable"
assert application_data_queries == 0

print(f"global_rows={global_first.row_count}")
print(f"global_repeat_sha256={global_hash}")
print(f"context_alpha_rows={alpha_first.row_count}")
print(f"context_alpha_repeat_sha256={alpha_hash}")
print(f"context_bravo_rows={bravo_result.row_count}")
print(f"context_bravo_sha256={bravo_hash}")
print("context_hashes_differ=true")
print("denial_status=blocked")
print(f"denial_code={denial_code}")
print(f"denial_application_data_queries={application_data_queries}")
PY

(
  cd "$project_root"
  "$venv/bin/python" manage.py makemigrations shop --noinput --verbosity 0
  "$venv/bin/python" manage.py migrate --noinput --verbosity 0
  "$venv/bin/python" manage.py check
  "$venv/bin/python" core_smoke.py
)

echo "PASS core quickstart exact-wheel smoke"
