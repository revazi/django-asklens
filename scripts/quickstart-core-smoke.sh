#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/quickstart-core-smoke.sh [--api] [--help]

Build one wheel from the current tracked local source files and exercise one
fresh disposable synthetic Django project. The default mode installs that exact
wheel with core dependencies only and preserves the U2 trusted-core smoke.
`--api` installs the same exact wheel with its optional API extra and proves the
current authenticated catalog/query/audit path. Normal package build and
dependency installation may use configured package indexes. Neither mode calls
a live provider, container, frontend, or MCP surface.
EOF
}

mode="core"
case "${1:-}" in
  "") ;;
  --api)
    mode="api"
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
install_target="$wheel"
if [[ "$mode" == "api" ]]; then
  install_target="${wheel}[api]"
fi
install_log="$workdir/install.log"
if ! "$venv/bin/python" -m pip install --no-cache-dir "$install_target" \
  >"$install_log" 2>&1; then
  tail -n 80 "$install_log" >&2
  exit 1
fi

# Prove exact direct-wheel provenance and installed package bytes in both modes.
# The core default remains optional-dependency-free; API mode contains DRF only.
"$venv/bin/python" - "$wheel" "$mode" <<'PY'
from importlib import metadata, util
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse
import zipfile

wheel = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
distribution = metadata.distribution("django-asklens")
direct_url_text = distribution.read_text("direct_url.json")
if direct_url_text is None:
    raise SystemExit("Exact local wheel installation has no direct_url.json.")
direct_url = json.loads(direct_url_text)
parsed = urlparse(direct_url["url"])
installed_from = Path(unquote(parsed.path)).resolve()
if installed_from != wheel:
    raise SystemExit("Isolated install did not use the exact locally built wheel.")

requirements = distribution.requires or []
api_requirements = [
    requirement
    for requirement in requirements
    if requirement.lower().startswith("djangorestframework")
]
mcp_requirements = [
    requirement
    for requirement in requirements
    if requirement.lower().startswith("fastmcp")
]


def guarded_by_extra(requirement: str, extra: str) -> bool:
    marker = requirement.partition(";")[2].lower().replace("'", '"').replace(" ", "")
    return f'extra=="{extra}"' in marker


if len(api_requirements) != 1 or not guarded_by_extra(api_requirements[0], "api"):
    raise SystemExit("The wheel no longer keeps DRF behind only the API extra.")
if len(mcp_requirements) != 1 or not guarded_by_extra(mcp_requirements[0], "mcp"):
    raise SystemExit("The wheel no longer keeps FastMCP behind only the MCP extra.")

if mode == "api":
    if util.find_spec("rest_framework") is None:
        raise SystemExit("DRF is absent from the API-extra environment.")
else:
    if util.find_spec("rest_framework") is not None:
        raise SystemExit("DRF unexpectedly appeared in the core-only environment.")
if util.find_spec("fastmcp") is not None:
    raise SystemExit("FastMCP unexpectedly appeared outside the MCP environment.")

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
print("core_optional_dependency_status=guarded")
if mode == "api":
    print("api_install_status=exact-wheel-api-extra")
else:
    print("core_install_status=exact-wheel-core-only")
PY

"$venv/bin/django-admin" startproject quickstart "$project_root"
(
  cd "$project_root"
  "$venv/bin/python" manage.py startapp shop
)

if [[ "$mode" == "api" ]]; then
  cat >"$project_root/quickstart/settings.py" <<'PY'
"""Disposable authenticated-API settings using only synthetic SQLite data."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "synthetic-api-quickstart-only"
DEBUG = False
ALLOWED_HOSTS = ["testserver"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "django_asklens",
    "shop.apps.ShopConfig",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
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
    "DUMMY_PLANS": {
        "List current scoped facts": {
            "query_plan": {
                "resource": "scoped_facts",
                "intent": "list",
                "select": ["summary"],
                "order_by": [{"field": "summary", "direction": "asc"}],
                "limit": 20,
            },
            "presentation": {"kind": "table"},
        }
    },
    "AUDIT_MODE": "database",
    "AUDIT_INCLUDE_CONTENT": False,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {
        "django.request": {"handlers": ["null"], "propagate": False},
    },
}
PY

  cat >"$project_root/quickstart/urls.py" <<'PY'
"""Mount only the current optional AskLens API in this disposable project."""

from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
PY

  cat >"$project_root/shop/models.py" <<'PY'
"""Synthetic host model for the authenticated API quickstart."""

from django.conf import settings
from django.db import models


class ScopedFact(models.Model):
    """Data whose owner remains a private host-side scope detail."""

    scope_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    internal_label = models.CharField(max_length=100)
PY

  cat >"$project_root/shop/asklens_registration.py" <<'PY'
"""The one project-owned AskLens registration module."""

from django_asklens import register

from .models import ScopedFact

RESOURCE_PERMISSION = "shop.view_scopedfact"


def visible_scoped_facts(request):
    """Resolve rows only from the current authenticated server-owned identity."""

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return ScopedFact.objects.none()
    return ScopedFact.objects.filter(scope_owner=user)


register(
    timezone="UTC",
    model=ScopedFact,
    name="scoped_facts",
    label="Scoped facts",
    description="Synthetic facts visible to the current authenticated user.",
    fields={
        "summary": {
            "binding": "internal_label",
            "type": "string",
            "nullable": False,
            "label": "Summary",
        },
    },
    default_order=(("summary", "asc"),),
    requires_permission=RESOURCE_PERMISSION,
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

  cat >"$project_root/api_smoke.py" <<'PY'
"""Exercise current session-authenticated API, scope, denial, and audit behavior."""

import hashlib
import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quickstart.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from django_asklens.models import SemanticQueryRun
from shop.asklens_registration import RESOURCE_PERMISSION
from shop.models import ScopedFact

QUESTION = "List current scoped facts"


def logged_in_client(user):
    """Use normal Django session authentication in the disposable host."""

    client = Client()
    client.force_login(user)
    return client


def stable_projection(payload):
    """Exclude caller echo, run id, and timing from deterministic comparison."""

    return {
        key: payload[key]
        for key in (
            "response_type",
            "plan",
            "columns",
            "data",
            "row_count",
            "result_metadata",
            "presentation",
            "explanation",
        )
    }


def projection_sha256(payload):
    """Hash canonical authorized output without printing response rows."""

    encoded = json.dumps(
        stable_projection(payload),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def nested_keys(value):
    """Yield all serialized mapping keys without retaining payload output."""

    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from nested_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from nested_keys(item)


User = get_user_model()
authorized_user = User.objects.create_user(username="api-authorized")
denied_user = User.objects.create_user(username="api-denied")
other_scope_user = User.objects.create_user(username="api-other-scope")
assert all(
    user.is_authenticated and not user.is_staff and not user.is_superuser
    for user in (authorized_user, denied_user, other_scope_user)
)
view_permission = Permission.objects.get(
    content_type__app_label="shop",
    codename="view_scopedfact",
)
assert f"{view_permission.content_type.app_label}.{view_permission.codename}" == (
    RESOURCE_PERMISSION
)
authorized_user.user_permissions.add(view_permission)
authorized_user = User.objects.get(pk=authorized_user.pk)

ScopedFact.objects.bulk_create(
    [
        ScopedFact(
            scope_owner=authorized_user,
            internal_label="First authorized synthetic fact",
        ),
        ScopedFact(
            scope_owner=authorized_user,
            internal_label="Second authorized synthetic fact",
        ),
        ScopedFact(
            scope_owner=other_scope_user,
            internal_label="Other-scope synthetic fact",
        ),
    ]
)

private_keys = {
    "binding",
    "model",
    "model_label",
    "password",
    "permission",
    "requires_permission",
    "scope_key",
    "scope_mode",
    "scope_owner",
    "scope_provider",
    "tenant",
}
private_values = {
    RESOURCE_PERMISSION,
    "internal_label",
    "scope_owner",
    "shop.ScopedFact",
    ScopedFact._meta.db_table,
    authorized_user.get_username(),
    denied_user.get_username(),
    other_scope_user.get_username(),
    "Other-scope synthetic fact",
}

# Catalog first: an authorized normal user's document contains only public
# semantics, while another authenticated user cannot see the hidden resource.
authorized_client = logged_in_client(authorized_user)
catalog_response = authorized_client.get("/asklens/catalog/")
assert catalog_response.status_code == 200
catalog_payload = catalog_response.json()
assert [resource["name"] for resource in catalog_payload["resources"]] == [
    "scoped_facts"
]
[resource] = catalog_payload["resources"]
assert [field["name"] for field in resource["fields"]] == ["summary"]
assert not (set(nested_keys(catalog_payload)) & private_keys)
catalog_text = json.dumps(catalog_payload, sort_keys=True)
assert all(value not in catalog_text for value in private_values)
assert "First authorized synthetic fact" not in catalog_text
assert "Second authorized synthetic fact" not in catalog_text

denied_client = logged_in_client(denied_user)
hidden_catalog_response = denied_client.get("/asklens/catalog/")
assert hidden_catalog_response.status_code == 200
assert hidden_catalog_response.json() == {"resources": []}
assert SemanticQueryRun.objects.count() == 0

# Route-level anonymous denials occur before AskLens orchestration and create no
# database audit row.
anonymous_client = Client()
anonymous_catalog_response = anonymous_client.get("/asklens/catalog/")
anonymous_query_response = anonymous_client.post(
    "/asklens/query/",
    data=json.dumps({"question": QUESTION}),
    content_type="application/json",
)
assert anonymous_catalog_response.status_code == 403
assert anonymous_query_response.status_code == 403
expected_authorization_error = {
    "error": {
        "code": "asklens.authorization.denied",
        "message": "The current request is not authorized.",
    }
}
assert anonymous_catalog_response.json() == expected_authorization_error
assert anonymous_query_response.json() == expected_authorization_error
assert SemanticQueryRun.objects.count() == 0

# Unknown top-level input, including client policy claims, is rejected before
# orchestration, audit, or registered application-data SQL.
client_policy_value = "private-client-permission-value"
with CaptureQueriesContext(connection) as strict_input_queries:
    strict_input_response = authorized_client.post(
        "/asklens/query/",
        data=json.dumps(
            {"question": QUESTION, "permissions": [client_policy_value]}
        ),
        content_type="application/json",
    )
assert strict_input_response.status_code == 400
assert strict_input_response.json() == {
    "error": {
        "code": "asklens.parse.invalid",
        "message": "The AskLens request could not be parsed.",
    }
}
assert client_policy_value not in json.dumps(strict_input_response.json())
application_table = ScopedFact._meta.db_table.lower()
assert all(
    application_table not in query["sql"].lower()
    for query in strict_input_queries.captured_queries
)
assert SemanticQueryRun.objects.count() == 0

# An authenticated principal without the resource permission receives only the
# current opaque member error, performs no registered application-data SQL, and
# creates one metadata-only failure record.
with CaptureQueriesContext(connection) as captured:
    denial_response = denied_client.post(
        "/asklens/query/",
        data=json.dumps({"question": QUESTION}),
        content_type="application/json",
    )
denial_payload = denial_response.json()
assert denial_response.status_code == 400
assert set(denial_payload) == {"error", "run_id"}
assert denial_payload["error"] == {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable.",
}
denial_code = denial_payload["error"]["code"]
assert denial_code == "asklens.member.unavailable"
denial_application_data_queries = sum(
    application_table in query["sql"].lower() for query in captured.captured_queries
)
assert denial_application_data_queries == 0
assert SemanticQueryRun.objects.count() == 1
assert all(value not in json.dumps(denial_payload) for value in private_values)

# The current authorized identity receives only its scoped rows. Repeat the
# request and compare a stable canonical response projection.
first_response = authorized_client.post(
    "/asklens/query/",
    data=json.dumps({"question": QUESTION}),
    content_type="application/json",
)
second_response = authorized_client.post(
    "/asklens/query/",
    data=json.dumps({"question": QUESTION}),
    content_type="application/json",
)
assert first_response.status_code == 200
assert second_response.status_code == 200
first_payload = first_response.json()
second_payload = second_response.json()
expected_response_keys = {
    "columns",
    "data",
    "duration_ms",
    "explanation",
    "plan",
    "presentation",
    "question",
    "response_type",
    "result_metadata",
    "row_count",
    "run_id",
}
assert set(first_payload) == expected_response_keys
assert set(second_payload) == expected_response_keys
assert first_payload["response_type"] == "query"
assert first_payload["row_count"] == 2
assert second_payload["row_count"] == 2
assert first_payload["columns"] == [
    {"key": "summary", "label": "Summary", "type": "string", "nullable": False}
]
expected_rows = [
    {"summary": "First authorized synthetic fact"},
    {"summary": "Second authorized synthetic fact"},
]
assert first_payload["data"] == expected_rows
assert second_payload["data"] == expected_rows
assert first_payload["plan"]["resource"] == "scoped_facts"
assert first_payload["plan"]["intent"] == "list"
assert set(first_payload["plan"]) == {
    "filters",
    "group_by",
    "intent",
    "limit",
    "metrics",
    "order_by",
    "resource",
    "select",
}
first_hash = projection_sha256(first_payload)
second_hash = projection_sha256(second_payload)
assert first_hash == second_hash
for payload in (first_payload, second_payload):
    payload_text = json.dumps(payload, sort_keys=True)
    assert all(value not in payload_text for value in private_values)
    assert not (set(nested_keys(payload)) & private_keys)

# Database audit order is exact: one failed AskLens attempt, then two successes.
# Default metadata mode stores no question, rows, binding/policy details, or
# provider envelope; accepted plans keep only operational resource/intent keys.
runs = list(SemanticQueryRun.objects.order_by("id"))
statuses = [run.status for run in runs]
assert statuses == ["failed", "success", "success"]
assert len(runs) == 3
assert all(run.question == "" for run in runs)
assert runs[0].plan == {}
assert runs[0].row_count == 0
assert runs[0].error.startswith("asklens.member.unavailable:")
for run in runs:
    assert set(run.plan) <= {"resource", "intent"}
for run in runs[1:]:
    assert run.plan == {"resource": "scoped_facts", "intent": "list"}
    assert run.row_count == 2
    assert run.error == ""
audit_text = json.dumps(
    [
        {
            "error": run.error,
            "plan": run.plan,
            "question": run.question,
            "row_count": run.row_count,
            "status": run.status,
        }
        for run in runs
    ],
    sort_keys=True,
)
assert QUESTION not in audit_text
assert all(value not in audit_text for value in private_values)
for forbidden_audit_content in (
    "First authorized synthetic fact",
    "Second authorized synthetic fact",
    "query_plan",
    "presentation",
    "filters",
    "select",
):
    assert forbidden_audit_content not in audit_text

print(f"api_catalog_status={catalog_response.status_code}")
print(f"api_catalog_resource_count={len(catalog_payload['resources'])}")
print(f"api_hidden_catalog_resource_count={len(hidden_catalog_response.json()['resources'])}")
print(f"api_anonymous_catalog_status={anonymous_catalog_response.status_code}")
print(f"api_anonymous_query_status={anonymous_query_response.status_code}")
print("api_anonymous_audit_count=0")
print(f"api_member_denial_status={denial_response.status_code}")
print(f"api_member_denial_code={denial_code}")
print(f"api_member_denial_application_data_queries={denial_application_data_queries}")
print(f"api_success_first_status={first_response.status_code}")
print(f"api_success_second_status={second_response.status_code}")
print(f"api_success_row_count={first_payload['row_count']}")
print(f"api_success_repeat_sha256={first_hash}")
print("api_success_repeat_stable=true")
print(f"api_audit_count={len(runs)}")
print(f"api_audit_statuses={','.join(statuses)}")
print("api_audit_questions_blank=true")
print("api_audit_plans_metadata_only=true")
print("api_private_metadata_absent=true")
PY

  (
    cd "$project_root"
    setup_log="$workdir/api-django-setup.log"
    if ! {
      "$venv/bin/python" manage.py makemigrations shop --noinput --verbosity 0
      "$venv/bin/python" manage.py migrate --noinput --verbosity 0
      "$venv/bin/python" manage.py check --verbosity 0
    } >"$setup_log" 2>&1; then
      tail -n 80 "$setup_log" >&2
      exit 1
    fi
    "$venv/bin/python" api_smoke.py
  )

  echo "PASS authenticated API quickstart exact-wheel smoke"
  exit 0
fi

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
