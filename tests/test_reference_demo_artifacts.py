"""Offline checks for the opt-in PostgreSQL reference-demo evidence."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "compose.yaml"
REFERENCE_SCRIPT = ROOT / "scripts" / "reference-demo-smoke.sh"
PACKAGE_SCRIPT = ROOT / "scripts" / "alpha-candidate-package-smoke.sh"
CORE_QUICKSTART_SCRIPT = ROOT / "scripts" / "quickstart-core-smoke.sh"
CORE_QUICKSTART_GUIDE = ROOT / "docs" / "quickstart-core.md"
PLAYWRIGHT_TEST = ROOT / "tests" / "e2e" / "reference_demo.py"
FRONTEND_TEMPLATE = (
    ROOT / "django_asklens" / "templates" / "django_asklens" / "frontend" / "query.html"
)
DEMO_VIEW = ROOT / "tests" / "test_project" / "demo_views.py"
DEMO_DENIAL_TEMPLATE = (
    ROOT
    / "tests"
    / "test_project"
    / "templates"
    / "test_project"
    / "asklens_demo_denied.html"
)
PRIVATE_EVALUATION_GUIDE = ROOT / "docs" / "private-candidate-evaluation.md"
PILOT_INTAKE_WORKSHEET = ROOT / "docs" / "pilot-intake-worksheet.md"
PERFORMANCE_SCRIPT = ROOT / "scripts" / "performance-baseline.sh"
PERFORMANCE_GUIDE = ROOT / "docs" / "performance-baseline.md"
HTTP_ENVELOPE_CROSSWALK = ROOT / "docs" / "http-internal-envelope-crosswalk.md"
WHEEL_SMOKE = ROOT / ".github" / "scripts" / "wheel_smoke.py"
API_SERIALIZERS = ROOT / "django_asklens" / "api" / "serializers.py"
API_VIEWS = ROOT / "django_asklens" / "api" / "views.py"


def read_text(path: Path) -> str:
    """Return one committed source artifact as UTF-8 text."""

    return path.read_text(encoding="utf-8")


def test_http_internal_envelope_crosswalk_maps_current_non_identity() -> None:
    """The API-2 map stays internal, source-bound, and explicit about wrappers."""

    assert HTTP_ENVELOPE_CROSSWALK.is_file()
    crosswalk = read_text(HTTP_ENVELOPE_CROSSWALK)

    for heading in (
        "# Current HTTP/internal-envelope crosswalk",
        "## Status, baseline, and evidence",
        "## Terms",
        "## Route and outcome matrix",
        "## `GET /asklens/catalog/`",
        "## `GET /asklens/capabilities/`",
        "## `POST /asklens/query/` success: query result",
        "## `POST /asklens/query/` success: capabilities and help",
        "## Errors and denials",
        "## `GET /asklens/runs/<int:pk>/`",
        "## Current non-identities and cleanup candidates",
        "## Recommended sequential cleanup order",
        "## Preserved security and package boundaries",
        "## Limitations",
    ):
        assert heading in crosswalk

    for term in (
        "**Internal document**",
        "**Exact document**",
        "**Embedded document**",
        "**HTTP adapter field**",
        "**Wrapper**",
        "**Transport/framework error**",
        "**Audit representation**",
    ):
        assert term in crosswalk

    matrix_header = (
        "| Route / outcome | Status | Body source | Internal-document relationship "
        "| Adapter fields | Audit effect | Current cleanup implication |"
    )
    assert matrix_header in crosswalk

    for source_link in (
        "../tests/api/test_http_characterization.py",
        "../django_asklens/api/views.py",
        "../django_asklens/querying.py",
        "../django_asklens/api/serializers.py",
        "../django_asklens/contracts/_models.py",
        "../tests/contracts/test_schemas.py",
        "internal-contracts.md",
        "conformance.md",
    ):
        assert source_link in crosswalk

    for document_name in (
        "`catalog`",
        "`capabilities`",
        "`query-plan`",
        "`result`",
        "`error`",
    ):
        assert document_name in crosswalk

    normalized = " ".join(crosswalk.split())
    for current_export_truth in (
        "API-3 removes the deprecated `django_asklens.api.querying` module and "
        "dead helper exports.",
        "`django_asklens.querying.__all__` is exactly `AskLensQueryResponse` and "
        "`execute_asklens_query_request`.",
        "`django_asklens.api.views.__all__` contains only `AskLensAPIView`, "
        "`CapabilitiesView`, `CatalogView`, `QueryRunDetailView`, and `QueryView`.",
        "Deliberate root `django_asklens` exports remain retained.",
        "Private `_build_success_payload()` and `_build_capabilities_payload()` "
        "helpers are implementation details, not supported imports.",
        "API-4a owns strict input and AskLens-route errors; API-4b owns success "
        "composition.",
        "API-6 remains the next separate packaging/import-parity PR after "
        "API-4b's post-merge gate.",
    ):
        assert current_export_truth in normalized

    for stale_api3_claim in (
        "`build_success_payload()`",
        "`build_capabilities_payload()`",
        "Assign compatibility/public-export inventory",
        "API-3 can remove",
        "does not authorize API-3",
        "open API-3",
    ):
        assert stale_api3_claim not in crosswalk

    for required in (
        "Schema validation is not authorization.",
        "not every HTTP body is an internal document",
        "strict `QueryRequestSerializer`",
        "one `{error, run_id?}` adapter shape",
        "complete exact `result` child",
        "`routing` and human `help`",
        "`help.content`",
        "MCP consumes the same shared result",
        "`WWW-Authenticate`",
        "`Retry-After`",
        "unrelated host DRF endpoints",
        "API-3",
        "API-4a",
        "API-4b",
        "API-5",
        "API-6",
        "authorization-filtered queryset",
        "asklens.view_semanticqueryrun",
        "AUDIT_DATABASE_ALIAS",
        "same fixed opaque `404`",
        "free-form field",
        "fixed generic safe error",
        "internal, draft, unfrozen, and unversioned",
        "not a public specification",
        "not a compatibility promise",
        "not an independent security audit",
    ):
        assert required in normalized

    for stale_shape in (
        '`{response_type: "error", error: {...}}`',
        '`{question, status: "failed", error, run_id?}`',
        "DRF `detail` errors.",
        "serializer behavior ignores unknown top-level request keys",
        "spreads `result` fields",
        "drops the core serializer's optional emitted `empty`",
        "`query_help_source`, `query_help`",
        "does not authorize API-4b",
        "could embed a complete `result` child",
    ):
        assert stale_shape not in crosswalk


def test_api4a_source_and_exact_wheel_evidence_are_strict_and_route_local() -> None:
    """Source and installed-wheel checks pin the breaking HTTP error boundary."""

    serializers = read_text(API_SERIALIZERS)
    views = read_text(API_VIEWS)
    wheel_smoke = read_text(WHEEL_SMOKE)

    assert "key not in self.fields" in serializers
    assert "The query request contains unsupported fields." in serializers
    for required in (
        "class AskLensAPIView(APIView)",
        "def handle_exception(self, exc: Exception) -> Response",
        'payload: dict[str, Any] = {"error": dict(error)}',
        '"asklens.authorization.denied"',
        '"asklens.budget.exceeded"',
        '"asklens.execute.failed"',
        'if outcome.response_type == "error"',
    ):
        assert required in views
    assert "EXCEPTION_HANDLER" not in views

    for required in (
        "APIRequestFactory",
        '"permissions": ["private-client-policy-value"]',
        "strict_response.status_code == 400",
        '"code": "asklens.parse.invalid"',
        'method_response["Allow"] == "GET, HEAD, OPTIONS"',
        "method_response.status_code == 405",
    ):
        assert required in wheel_smoke


def test_package_provenance_separates_published_and_unreleased_docs() -> None:
    """Published, source, and private-candidate instructions cannot be confused."""

    readme = read_text(ROOT / "README.md")
    index = read_text(ROOT / "docs" / "index.md")
    install = read_text(ROOT / "docs" / "installation.md")
    tagged_docs = "https://github.com/revazi/django-asklens/blob/v0.1.0a1/README.md"

    provenance_heading = "## Package provenance: published alpha versus main"
    main_quickstart_heading = (
        "## Unreleased main quickstart (not for published 0.1.0a1)"
    )
    assert provenance_heading in readme
    assert "PyPI currently serves `django-asklens==0.1.0a1`" in readme
    assert "unreleased, incompatible 0.2 target" in readme
    assert "No public 0.2 package is being released by this PR." in readme
    assert "python -m pip install 'django-asklens==0.1.0a1'" in readme
    assert tagged_docs in readme
    assert main_quickstart_heading in readme
    assert readme.index(provenance_heading) < readme.index("## What it provides")
    assert readme.index(provenance_heading) < readme.index(main_quickstart_heading)
    assert readme.index("unreleased, incompatible 0.2 target") < readme.index(
        main_quickstart_heading
    )
    assert "python -m pip install 'django-asklens[api]'" not in readme

    published_heading = "## Published PyPI alpha: 0.1.0a1"
    source_heading = "## Unreleased main/source checkout for contributors"
    candidate_heading = "## Maintainer-supplied private candidate evaluation"
    for heading in (published_heading, source_heading, candidate_heading):
        assert heading in install
    assert install.index(published_heading) < install.index(source_heading)
    assert install.index(source_heading) < install.index(candidate_heading)

    published_section = install[
        install.index(published_heading) : install.index(source_heading)
    ]
    published_commands = [
        line
        for line in published_section.splitlines()
        if line.startswith("python -m pip install")
    ]
    assert published_commands == [
        "python -m pip install 'django-asklens==0.1.0a1'",
        "python -m pip install 'django-asklens[api]==0.1.0a1'",
        "python -m pip install 'django-asklens[mcp]==0.1.0a1'",
    ]
    assert tagged_docs in published_section

    source_section = install[
        install.index(source_heading) : install.index(candidate_heading)
    ]
    assert "not a release or release candidate" in source_section
    assert "not a PyPI upgrade" in source_section
    assert "### Source-checkout alpha-candidate package evidence" in source_section
    assert "same-version replacement evidence" in source_section
    assert "not a normal upgrade or release" in source_section

    candidate_section = install[install.index(candidate_heading) :]
    guide_link = (
        "[private candidate evaluation and onboarding guide]"
        "(private-candidate-evaluation.md)"
    )
    for marker in (
        "immutable 40-character Git commit",
        "exact wheel filename",
        "SHA-256 digest",
    ):
        assert marker in candidate_section
        assert candidate_section.index(marker) < candidate_section.index(guide_link)
    assert "verify all three before installing" in candidate_section
    assert candidate_section.index("verify all three before installing") < (
        candidate_section.index(guide_link)
    )
    assert "not a normal PyPI upgrade or public release" in candidate_section

    index_heading = "## Package provenance: choose documentation by artifact"
    assert index_heading in index
    assert index.index(index_heading) < index.index("## Guides")
    assert "PyPI currently serves `django-asklens==0.1.0a1`" in index
    assert "unreleased, incompatible 0.2 target" in index
    assert (
        "No public 0.2 package is being released by this documentation change." in index
    )
    assert tagged_docs in index

    for local_document in (
        ROOT / "docs" / "installation.md",
        ROOT / "docs" / "private-candidate-evaluation.md",
    ):
        assert local_document.is_file()


def test_core_quickstart_is_linear_executable_and_fail_closed() -> None:
    """The unreleased core golden path stays complete, explicit, and disposable."""

    assert CORE_QUICKSTART_GUIDE.is_file()
    assert CORE_QUICKSTART_SCRIPT.is_file()
    assert CORE_QUICKSTART_SCRIPT.stat().st_mode & 0o111

    guide = read_text(CORE_QUICKSTART_GUIDE)
    readme = read_text(ROOT / "README.md")
    index = read_text(ROOT / "docs" / "index.md")
    core_api = read_text(ROOT / "docs" / "core-python-api.md")
    registration = read_text(ROOT / "docs" / "registration.md")
    script = read_text(CORE_QUICKSTART_SCRIPT)

    ordered_headings = (
        "## Artifact boundary",
        "## 1. Install the exact core artifact",
        "## 2. Create the models",
        "## 3. Register the reviewed resources",
        "## 4. Import registration once from `AppConfig.ready()`",
        "## 5. Migrate and check",
        "## 6. Execute untrusted list plans with current requests",
        "## 7. Run the disposable wheel smoke",
    )
    positions = [guide.index(heading) for heading in ordered_headings]
    assert positions == sorted(positions)

    normalized_guide = " ".join(guide.replace("\n> ", " ").split())
    for required in (
        "unreleased current source",
        "separately verified exact candidate wheel",
        "not the published PyPI `0.1.0a1`",
        'scope_mode="global"',
        'scope_mode="context_scoped"',
        "scope_provider=visible_scoped_facts",
        '"select": ["code", "label"]',
        '"select": ["label"]',
        "execute_plan(global_plan, request=request)",
        "execute_plan(scoped_plan, request=request)",
        "asklens.member.unavailable",
        "zero registered application-data SQL",
        "server-owned",
        "does not autodiscover",
        "URLs, models, admin modules, multiple `AppConfig` classes",
        "autoreloader",
    ):
        assert " ".join(required.split()) in normalized_guide

    assert "[Core-only executable quickstart](docs/quickstart-core.md)" in readme
    assert "[Core-only executable quickstart](quickstart-core.md)" in index
    assert "[core-only executable quickstart](quickstart-core.md)" in core_api
    assert "[core-only executable quickstart](quickstart-core.md)" in registration

    for required in (
        "set -Eeuo pipefail",
        "mktemp -d",
        "trap cleanup EXIT",
        'export TMPDIR="$process_tmp"',
        "python -m build --wheel",
        "python -m venv",
        "pip install --no-cache-dir",
        'util.find_spec("rest_framework")',
        'util.find_spec("fastmcp")',
        "startproject quickstart",
        "manage.py startapp shop",
        "manage.py makemigrations shop",
        "manage.py migrate",
        "manage.py check",
        '"select": ["code", "label"]',
        '"select": ["label"]',
        "RequestFactory",
        "execute_plan(",
        "CaptureQueriesContext",
        "asklens.member.unavailable",
        "application_data_queries == 0",
        "PASS core quickstart exact-wheel smoke",
    ):
        assert required in script

    assert 'mode="core"' in script
    assert 'if [[ "$mode" == "api" ]]' in script
    assert 'install_target="$wheel"' in script
    assert "[mcp]" not in script
    assert "docker" not in script.lower()
    assert "twine upload" not in script
    assert "git push" not in script
    assert "rm -rf" not in script
    assert "OPENAI" not in script
    subprocess.run(["bash", "-n", CORE_QUICKSTART_SCRIPT], check=True, cwd=ROOT)


def test_authenticated_api_quickstart_is_current_private_and_disposable() -> None:
    """The optional API path is linear without changing its current contract."""

    readme = read_text(ROOT / "README.md")
    install = read_text(ROOT / "docs" / "installation.md")
    usage = read_text(ROOT / "docs" / "usage.md")
    security = read_text(ROOT / "docs" / "security-checklist.md")
    script = read_text(CORE_QUICKSTART_SCRIPT)

    readme_link = (
        "[Authenticated normal-user API quickstart]"
        "(docs/usage.md#authenticated-normal-user-api-quickstart)"
    )
    assert readme_link in readme
    assert "catalog first" in readme.lower()
    assert "host-created authenticated user" in readme
    assert "does not provide a login or token endpoint" in readme

    install_heading = "## Authenticated API prerequisites for exact current artifacts"
    assert install_heading in install
    install_section = install[install.index(install_heading) :]
    for required in (
        "exact verified wheel",
        "[api]",
        '"rest_framework"',
        '"django.contrib.sessions"',
        '"django.contrib.sessions.middleware.SessionMiddleware"',
        '"django.contrib.auth.middleware.AuthenticationMiddleware"',
        'include("django_asklens.api.urls")',
        "python -m django migrate",
        "existing host authentication",
        "does not add an authentication backend or token endpoint",
        "bash scripts/quickstart-core-smoke.sh --api",
    ):
        assert required in install_section

    usage_heading = "## Authenticated normal-user API quickstart"
    ordered_usage_headings = (
        usage_heading,
        "### 1. Install and mount the current optional API",
        "### 2. Register one context-scoped resource once",
        "### 3. Create and authorize a normal host user",
        "### 4. Verify the permission-scoped catalog first",
        "### 5. Submit the deterministic query",
        "### 6. Keep denials opaque and diagnose host setup",
        "### 7. Verify metadata-only audit outcomes",
    )
    usage_positions = [usage.index(heading) for heading in ordered_usage_headings]
    assert usage_positions == sorted(usage_positions)
    normalized_usage = " ".join(usage.replace("\n> ", " ").split())
    for required in (
        "unreleased current source",
        "separately verified exact candidate",
        "not the published PyPI `0.1.0a1`",
        "normal user",
        "server-owned",
        "AppConfig.ready()",
        "force_login",
        "GET /asklens/catalog/",
        "POST /asklens/query/",
        "HTTP 403",
        "HTTP 400",
        "HTTP 200",
        "asklens.member.unavailable",
        "zero registered application-data SQL",
        "one failed audit row",
        "one success audit row",
        "AUDIT_INCLUDE_CONTENT=False",
        "question is blank",
        "resource and intent",
        "bindings, permission tokens, model labels, scope identifiers",
        "throttling, concurrency limits, statement timeout, and request timeout",
    ):
        assert " ".join(required.split()) in normalized_usage
    assert "requires_permission" in usage
    assert "must not appear in API, catalog, or audit responses" in usage

    normalized_security = " ".join(security.split())
    for required in (
        "anonymous catalog/query requests are rejected at the route gate",
        "server-owned permission assignment",
        "server-owned `scope_provider(request)`",
        "inspect the authenticated user's permission-scoped catalog first",
        "do not weaken `asklens.member.unavailable`",
        "metadata-only audit",
        "host-owned throttling, concurrency, database statement timeout, and "
        "request timeout",
    ):
        assert " ".join(required.split()) in normalized_security

    for required in (
        "Usage: bash scripts/quickstart-core-smoke.sh [--api] [--help]",
        'mode="core"',
        '--api)\n    mode="api"',
        'install_target="${wheel}[api]"',
        'util.find_spec("rest_framework")',
        'util.find_spec("fastmcp")',
        "core_optional_dependency_status=guarded",
        'ALLOWED_HOSTS = ["testserver"]',
        '"django.contrib.sessions"',
        '"rest_framework"',
        '"django.contrib.sessions.middleware.SessionMiddleware"',
        '"django.contrib.auth.middleware.AuthenticationMiddleware"',
        'include("django_asklens.api.urls")',
        '"AUDIT_MODE": "database"',
        '"AUDIT_INCLUDE_CONTENT": False',
        "AppConfig",
        "requires_permission=RESOURCE_PERMISSION",
        'scope_mode="context_scoped"',
        "client.force_login",
        'client.get("/asklens/catalog/")',
        "denied_client.post(",
        "authorized_client.post(",
        '"/asklens/query/"',
        "CaptureQueriesContext",
        "strict_input_response.status_code == 400",
        '"permissions": [client_policy_value]',
        '"code": "asklens.parse.invalid"',
        'set(denial_payload) == {"error", "run_id"}',
        'denial_code == "asklens.member.unavailable"',
        "denial_application_data_queries == 0",
        'statuses == ["failed", "success", "success"]',
        'run.question == ""',
        'set(run.plan) <= {"resource", "intent"}',
        "PASS authenticated API quickstart exact-wheel smoke",
    ):
        assert required in script

    for forbidden in (
        "rm -rf",
        "twine upload",
        "git push",
        "OPENAI_API_KEY",
        "TokenAuthentication",
        "obtain_auth_token",
    ):
        assert forbidden not in script
    subprocess.run(["bash", "-n", CORE_QUICKSTART_SCRIPT], check=True, cwd=ROOT)


def test_compose_defines_project_scoped_postgresql_18() -> None:
    """The source demo owns a healthy, disposable PostgreSQL 18 service."""

    compose = read_text(COMPOSE)

    assert "image: postgres:18" in compose
    assert "POSTGRES_DB: asklens_demo" in compose
    assert "POSTGRES_USER: asklens_demo" in compose
    assert "POSTGRES_PASSWORD: asklens-demo-only" in compose
    assert "pg_isready" in compose
    assert "condition: service_healthy" not in compose
    assert "127.0.0.1:${ASKLENS_COMPOSE_POSTGRES_PORT:-55432}:5432" in compose
    assert "postgres-data:/var/lib/postgresql" in compose
    assert "postgres-data:" in compose
    assert "container_name:" not in compose
    assert "5432:5432" not in compose


def test_reference_script_is_fail_fast_bounded_and_opt_in() -> None:
    """Orchestration cleans only its project and keeps unsafe modes disabled."""

    script = read_text(REFERENCE_SCRIPT)

    assert "set -Eeuo pipefail" in script
    assert "trap cleanup EXIT" in script
    assert "down --volumes --remove-orphans" in script
    assert "DJANGO_ASKLENS_POSTGRES_EXPECTED_MAJOR=18" in script
    assert "DJANGO_ASKLENS_DEMO_LIVE_LLM=0" in script
    assert "DJANGO_ASKLENS_MCP_ENABLED=1" in script
    assert "DJANGO_ASKLENS_MCP_USERNAME=facility-owner" in script
    assert "DJANGO_ASKLENS_MCP_ALLOW_ROWS=0" in script
    assert "seed_complex_test_project" in script
    assert "tests/e2e/reference_demo.py" in script
    assert "docker system prune" not in script
    assert "docker volume prune" not in script
    assert "rm -rf" not in script


def test_performance_baseline_script_is_bounded_and_safe() -> None:
    """Local baseline runner is deterministic, opt-in, and artifact-oriented."""

    script = read_text(PERFORMANCE_SCRIPT)

    assert "set -Eeuo pipefail" in script
    assert "run_performance_baseline" in script
    assert "seed_complex_test_project" in script
    assert "--dataset-profile" in script
    assert "--size PROFILE" in script
    assert "--query-profile" in script
    assert "--iterations" in script
    assert "--warmups" in script
    assert "--artifact-dir" in script
    assert "--artifact-name" in script
    assert "--output" in script
    assert "--commit" in script
    assert "--help" in script
    assert "--dataset-profile" in script
    assert (
        "${artifact_name}-${query_profile}-size${seed_profile}-i${iterations}-w"
        in script
    )
    assert "${warmups}" in script
    assert "resolve_commit" in script
    assert "git rev-parse" in script
    assert "SHOW server_version_num" not in script
    assert "connection.info.server_version" in script
    assert 'int("$PG_PORT")' not in script
    assert "PG_PORT" in script
    assert "trap - EXIT INT TERM" in script
    assert "No compose project started for this run; nothing to tear down." in script
    assert "DJANGO_ASKLENS_POSTGRES_EXPECTED_MAJOR=18" in script
    assert "DJANGO_ASKLENS_DEMO_LIVE_LLM=0" in script
    assert "compose down --volumes --remove-orphans" in script
    assert "trap cleanup EXIT" in script
    assert "Tore down compose project" in script
    assert "docker system prune" not in script
    assert "docker volume prune" not in script
    assert "rm -rf" not in script

    # Sanity check syntax and help output generation without running Docker.
    subprocess.run(["bash", "-n", str(PERFORMANCE_SCRIPT)], check=True)
    help_result = subprocess.run(
        ["bash", str(PERFORMANCE_SCRIPT), "--help"],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Usage:" in help_result.stdout

    safe_help_path = ROOT / ".asklens-performance-baseline" / "safe-help-output.json"
    safe_help_path.parent.mkdir(parents=True, exist_ok=True)
    if safe_help_path.exists():
        safe_help_path.unlink()
    help_with_output = subprocess.run(
        [
            "bash",
            str(PERFORMANCE_SCRIPT),
            "--output",
            str(safe_help_path),
            "--help",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Usage:" in help_with_output.stdout
    assert not safe_help_path.exists()


def test_playwright_test_uses_browser_and_network_surfaces() -> None:
    """Mandatory browser evidence cannot regress to a Django test client."""

    test_source = read_text(PLAYWRIGHT_TEST)

    assert "playwright.sync_api" in test_source
    assert "chromium.launch" in test_source
    assert ".request" in test_source
    assert '"tools/list"' in test_source
    assert '"tools/call"' in test_source
    assert "asklens_execute_plan" in test_source
    assert "row_return_denied" in test_source
    assert "django.test" not in test_source
    assert "APIClient" not in test_source
    assert "Client(" not in test_source


def test_package_evidence_is_isolated_and_never_releases() -> None:
    """Candidate checks build/install/upgrade locally without publication."""

    script = read_text(PACKAGE_SCRIPT)

    assert "mktemp -d" in script
    assert "django-asklens==0.1.0a1" in script
    assert "--force-reinstall" in script
    assert "wheel-smoke.sh" in script
    assert "core api mcp" in script
    assert "coverage" in script
    assert '"httpx"' in script
    assert '"jsonschema"' in script
    assert "Draft202012Validator" in script
    assert "source wheel query schema enforces containment value constraints" in script
    assert "playwright" in script
    assert "psycopg" in script
    assert "docker" in script
    assert "twine upload" not in script
    assert "git tag" not in script
    assert "git push" not in script
    assert "0.2.0a" not in read_text(ROOT / "pyproject.toml")


def test_package_migration_probe_is_disposable_and_scoped() -> None:
    """Package smoke validates SQLite same-version migration-state preservation."""

    script = read_text(PACKAGE_SCRIPT)

    assert "migration-probe" in script
    assert "ASKLENS_MIGRATION_PROBE_DB" in script
    assert "ASKLENS_MIGRATION_PROBE_SECRET" in script
    assert "probe.sqlite3" in script
    assert 'probe_plan_output="$(probe_manage migrate --plan 2>&1)"' in script
    assert "probe_python - <<'PY'" in script
    assert "probe_manage migrate" in script
    assert "MigrationRecorder" in script
    assert "MigrationExecutor" in script
    assert "connection.introspection.table_names" in script
    assert "AskLensQuery._meta.proxy" in script
    assert "AskLensQuery._meta.db_table" in script
    assert "SemanticQueryRun.objects.get()" in script
    assert "synthetic published probe" in script
    assert (
        "PASS published migration graph is exact: 0001_initial and"
        " 0002_add_admin_query_proxy" in script
    )
    assert (
        "PASS published 0.1.0a1 migration state initialized with "
        "one synthetic row" in script
    )
    assert (
        "PASS migration graph after local same-version replacement is"
        " exact: 0001_initial and 0002_add_admin_query_proxy" in script
    )
    assert (
        script.count(
            "asklens_migrations == {"
            '("asklens", "0001_initial"), '
            '("asklens", "0002_add_admin_query_proxy")}'
        )
        == 2
    )
    assert "cursor.execute(" not in script
    assert "sqlite3.connect" not in script
    assert "raw SQL" not in script.lower()
    assert "0.1.0a1 to 0.2" not in script.lower()


def test_httpx_is_an_explicit_locked_development_dependency() -> None:
    """The ASGI test client must not rely on MCP's transitive dependencies."""

    metadata = tomllib.loads(read_text(ROOT / "pyproject.toml"))
    lock = tomllib.loads(read_text(ROOT / "uv.lock"))

    assert "httpx>=0.28.1,<0.29" in metadata["dependency-groups"]["dev"]
    asklens = next(
        package for package in lock["package"] if package["name"] == "django-asklens"
    )
    assert {"name": "httpx"} in asklens["dev-dependencies"]["dev"]
    assert {"name": "httpx", "specifier": ">=0.28.1,<0.29"} in asklens["metadata"][
        "requires-dev"
    ]["dev"]


def test_jsonschema_is_an_explicit_locked_development_dependency() -> None:
    """Independent contract validation must not rely on a transitive tool."""

    metadata = tomllib.loads(read_text(ROOT / "pyproject.toml"))
    lock = tomllib.loads(read_text(ROOT / "uv.lock"))

    assert "jsonschema>=4.26,<5" in metadata["dependency-groups"]["dev"]
    asklens = next(
        package for package in lock["package"] if package["name"] == "django-asklens"
    )
    assert {"name": "jsonschema"} in asklens["dev-dependencies"]["dev"]
    assert {"name": "jsonschema", "specifier": ">=4.26,<5"} in asklens["metadata"][
        "requires-dev"
    ]["dev"]


def test_dev_tools_do_not_leak_into_runtime_metadata() -> None:
    """Test and source-only tools remain absent from install requirements."""

    metadata = tomllib.loads(read_text(ROOT / "pyproject.toml"))
    runtime = "\n".join(metadata["project"]["dependencies"]).lower()
    extras = "\n".join(
        dependency
        for requirements in metadata["project"]["optional-dependencies"].values()
        for dependency in requirements
    ).lower()

    for forbidden in (
        "coverage",
        "docker",
        "httpx",
        "jsonschema",
        "playwright",
        "psycopg",
    ):
        assert forbidden not in runtime
        assert forbidden not in extras
    assert metadata["project"]["version"] == "0.1.0a1"


def test_reference_shell_entrypoints_have_safe_argument_boundaries() -> None:
    """Help/argument checks run without Docker, PostgreSQL, or browsers."""

    for script in (REFERENCE_SCRIPT, PACKAGE_SCRIPT):
        subprocess.run(["bash", "-n", script], check=True, cwd=ROOT)
        help_result = subprocess.run(
            ["bash", script, "--help"],
            check=False,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert help_result.returncode == 0
        assert "Usage:" in help_result.stdout

    invalid = subprocess.run(
        ["bash", REFERENCE_SCRIPT, "--not-a-mode"],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode == 2
    assert "Unknown option" in invalid.stderr


def test_ci_explicitly_covers_supported_django_lines() -> None:
    """CI pins 5.2, 6.0, and 6.1 without floating the protected alias."""

    import re

    workflow = read_text(ROOT / ".github" / "workflows" / "ci.yml")
    package_script = read_text(PACKAGE_SCRIPT)

    test_match = re.search(r"  test:(.*?)  postgresql:", workflow, re.DOTALL)
    assert test_match is not None, "Could not find SQLite/full-suite job"
    test_job = test_match.group(1)

    assert 'django-version: ["5.2", "6.0", "6.x"]' in test_job
    expected_sqlite_bands = (
        (
            'django-version: "5.2"\n'
            '            django-package: "Django>=5.2,<5.3"\n'
            '            django-version-prefix: "5.2."'
        ),
        (
            'django-version: "6.0"\n'
            '            django-package: "Django>=6.0,<6.1"\n'
            '            django-version-prefix: "6.0."'
        ),
        (
            'django-version: "6.x"\n'
            '            django-package: "Django>=6.1,<6.2"\n'
            '            django-version-prefix: "6.1."'
        ),
    )
    for expected in expected_sqlite_bands:
        assert expected in test_job

    assert "The protected 6.x check names remain fixed to Django 6.1" in test_job
    assert (
        "name: Python ${{ matrix.python-version }} / "
        "Django ${{ matrix.django-version }}"
    ) in test_job
    assert "pytest --strict-config --strict-markers" in test_job
    for mode in ("core", "api", "mcp"):
        assert (
            f"{mode} \\\n"
            '            "${{ matrix.django-package }}" \\\n'
            '            "${{ matrix.django-version-prefix }}"'
        ) in test_job

    assert "Django>=6.0,<7.0" not in workflow
    assert "Django>=5.2,<6.0" not in workflow

    postgresql_match = re.search(
        r"  postgresql:(.*?)  reference-demo:", workflow, re.DOTALL
    )
    assert postgresql_match is not None, "Could not find PostgreSQL job"
    postgresql_job = postgresql_match.group(1)
    for version, package, prefix in (
        ("5.2", "Django>=5.2,<5.3", "5.2."),
        ("6.0", "Django>=6.0,<6.1", "6.0."),
        ("6.1", "Django>=6.1,<6.2", "6.1."),
    ):
        assert f'django-version: "{version}"' in postgresql_job
        assert f'django-package: "{package}"' in postgresql_job
        assert f'django-version-prefix: "{prefix}"' in postgresql_job
    assert "name: Guard Django matrix version" in postgresql_job

    for job_name in ("reference-demo", "candidate-package"):
        job_match = re.search(
            rf"  {job_name}:(.*?)(?=\n  [a-z][a-z-]+:|\Z)", workflow, re.DOTALL
        )
        assert job_match is not None, f"Could not find {job_name} job"
        assert "name: Guard lock-selected Django 6.1" in job_match.group(1)
        assert 'DJANGO_VERSION_PREFIX: "6.1."' in job_match.group(1)

    assert '"Django>=6.1,<6.2" \\\n    "6.1."' in package_script
    assert "Django>=6.0,<7.0" not in package_script


def test_django_61_dependency_pair_is_locked_and_drf_stays_optional() -> None:
    """The optional API uses the Django-6.1-compatible DRF line."""

    project = tomllib.loads(read_text(ROOT / "pyproject.toml"))
    lock = tomllib.loads(read_text(ROOT / "uv.lock"))

    drf_requirement = "djangorestframework>=3.18,<4.0"
    assert project["project"]["optional-dependencies"]["api"] == [drf_requirement]
    assert drf_requirement in project["dependency-groups"]["dev"]
    assert all(
        not requirement.lower().startswith("djangorestframework")
        for requirement in project["project"]["dependencies"]
    )

    locked_versions = {
        package["name"]: package["version"] for package in lock["package"]
    }
    assert locked_versions["django"].startswith("6.1")
    assert locked_versions["djangorestframework"].startswith("3.18")


def test_django_install_range_is_not_a_future_ci_support_claim() -> None:
    """The broad resolver cap is distinct from currently tested Django lines."""

    project = tomllib.loads(read_text(ROOT / "pyproject.toml"))
    django_requirements = [
        requirement
        for requirement in project["project"]["dependencies"]
        if requirement.lower().startswith("django")
    ]
    assert django_requirements == ["Django>=5.2,<7.0"]
    assert {
        "Framework :: Django :: 5.2",
        "Framework :: Django :: 6.0",
        "Framework :: Django :: 6.1",
    } <= set(project["project"]["classifiers"])

    support_boundary = (
        "Installation metadata remains `Django>=5.2,<7.0`, but current CI support "
        "evidence is deliberately limited to Django 5.2 LTS, 6.0, and 6.1."
    )
    for relative_path in (
        "README.md",
        "docs/installation.md",
        "docs/private-candidate-evaluation.md",
    ):
        assert support_boundary in read_text(ROOT / relative_path)


def test_postgresql_ci_matrix_is_parameterized() -> None:
    """The PostgreSQL CI matrix covers exactly the three authorized stacks."""

    import re

    workflow = read_text(ROOT / ".github" / "workflows" / "ci.yml")

    # Extract the postgresql job block.
    job_match = re.search(r"  postgresql:(.*?)  reference-demo:", workflow, re.DOTALL)
    assert job_match is not None, "Could not find postgresql job in CI workflow"
    job = job_match.group(1)

    # Assert dynamic job name.
    job_name = (
        "name: PostgreSQL ${{ matrix.postgresql-version }} / "
        "Python ${{ matrix.python-version }} / "
        "Django ${{ matrix.django-version }}"
    )
    assert job_name in job

    # Extract the matrix include block.
    include_match = re.search(r"        include:(.*?)\n    services:", job, re.DOTALL)
    assert include_match is not None, "Could not find matrix include block"
    include = include_match.group(1)

    # Verify exactly three combinations.
    entries = re.findall(r"- postgresql-version:", include)
    assert len(entries) == 3, f"Expected exactly 3 matrix entries, got {len(entries)}"

    # Verify the specific authorized tuples as units.
    expected_tuples = [
        (
            '- postgresql-version: "15"\n'
            '            python-version: "3.12"\n'
            '            django-version: "5.2"\n'
            '            django-package: "Django>=5.2,<5.3"\n'
            '            django-version-prefix: "5.2."'
        ),
        (
            '- postgresql-version: "15"\n'
            '            python-version: "3.13"\n'
            '            django-version: "6.0"\n'
            '            django-package: "Django>=6.0,<6.1"\n'
            '            django-version-prefix: "6.0."'
        ),
        (
            '- postgresql-version: "18"\n'
            '            python-version: "3.13"\n'
            '            django-version: "6.1"\n'
            '            django-package: "Django>=6.1,<6.2"\n'
            '            django-version-prefix: "6.1."'
        ),
    ]
    for expected in expected_tuples:
        assert expected in include

    # Assert parameterized setup and install steps.
    assert "python-version: ${{ matrix.python-version }}" in job
    assert 'uv pip install --reinstall "${{ matrix.django-package }}"' in job
    assert "name: Guard Django matrix version" in job
    assert "DJANGO_VERSION_PREFIX: ${{ matrix.django-version-prefix }}" in job

    # Assert preservation of required execution steps.
    assert "name: Guard backend/version and replay all conformance fixtures" in job
    assert "tests/conformance/test_replay.py" in job
    assert "name: Run complete database-sensitive suite" in job
    assert "pytest --strict-config --strict-markers\n          -m postgresql" in job
    assert "name: Run PostgreSQL Django system check" in job
    check_command = (
        "python -m django check\n"
        "          --settings=tests.test_project.postgresql_settings"
    )
    assert check_command in job
    assert "name: Check AskLens migrations under PostgreSQL settings" in job
    migrate_command = (
        "python -m django makemigrations asklens\n"
        "          --check --dry-run "
        "--settings=tests.test_project.postgresql_settings"
    )
    assert migrate_command in job


def test_conformance_docs_match_current_postgresql_replay_evidence() -> None:
    """Document the actual replay matrix without claiming exhaustive coverage."""

    import re

    guide = read_text(ROOT / "docs" / "conformance.md")
    workflow = read_text(ROOT / ".github" / "workflows" / "ci.yml")
    job_match = re.search(r"  postgresql:(.*?)  reference-demo:", workflow, re.DOTALL)
    assert job_match is not None
    job = job_match.group(1)
    matrix = re.findall(
        r'- postgresql-version: "([^"]+)"\s+'
        r'python-version: "([^"]+)"\s+'
        r'django-version: "([^"]+)"',
        job,
    )
    assert matrix
    documented_matrix = re.findall(
        r"^\| (\d+) \| (\d+\.\d+) \| (\d+\.\d+) \|$", guide, re.MULTILINE
    )
    assert documented_matrix == matrix

    normalized = " ".join(guide.split())
    replay_command = (
        "uv run --no-sync pytest --strict-config --strict-markers "
        "-m postgresql tests/conformance/test_replay.py"
    )
    assert replay_command in " ".join(job.split())
    assert replay_command in normalized
    assert "../.github/workflows/ci.yml" in guide
    assert "../tests/conformance/test_replay.py" in guide
    for required in (
        "PostgreSQL replay runs in required CI",
        "server-major guard",
        "representative stacks, not a Cartesian matrix",
        "Passing the SQLite corpus does not provide PostgreSQL evidence",
        "not production certification, backend neutrality, or an independent "
        "security review",
    ):
        assert required in normalized
    assert "PostgreSQL replay is a later" not in normalized


def test_short_source_demo_is_scoped_offline_and_resettable() -> None:
    """U4 keeps one concise, browser-verified source-demo journey."""

    demo = read_text(ROOT / "docs" / "test-project-demo.md")
    candidate = read_text(PRIVATE_EVALUATION_GUIDE)
    readme = read_text(ROOT / "README.md")
    playwright = read_text(PLAYWRIGHT_TEST)

    heading = "## SQLite frontend and admin first run (start to reset)"
    next_heading = "## PostgreSQL 18 reference workflow"
    assert heading in demo
    section = demo[demo.index(heading) : demo.index(next_heading)]
    normalized = " ".join(section.split())

    for required in (
        "source checkout",
        "deterministic offline `DummyProvider`",
        "live providers disabled",
        "uv sync --locked --group dev",
        "seed_complex_test_project --size small",
        "runserver 127.0.0.1:8000",
        "username: `facility-owner`",
        "North Studio only",
        "Show paid billing revenue by product",
        "Offline dummy plans",
        "Raw response",
        "result.result_metadata",
        "metadata-only audit row",
        "username: `admin`",
        "superuser",
        "`/` — frontend data/help page",
        "`/admin/asklens/asklensquery/` — separate admin query/help page",
        "`/admin/asklens/semanticqueryrun/` — view-only audit page",
        "show me example queries",
        "does not create an audit row",
        "username: `no-report`",
        "HTTP status `403`",
        "Access unavailable",
        "Sign out and switch account",
        "Ctrl-C",
        "rm -f .asklens-test-project.sqlite3",
        "only this ignored synthetic SQLite file",
    ):
        assert " ".join(required.split()) in normalized

    assert section.index("username: `facility-owner`") < section.index(
        "username: `admin`"
    )
    assert "All demo facilities (superuser)" in section
    assert "question, complete plan, and result rows are omitted" in normalized

    demo_link = (
        "[source demo frontend/admin first run]"
        "(docs/test-project-demo.md#sqlite-frontend-and-admin-first-run-start-to-reset)"
    )
    assert demo_link in readme
    assert "test-project-demo.md#postgresql-18-reference-workflow" in candidate
    assert (
        "test-project-demo.md#one-command-postgresql-18--playwright-reference"
        not in candidate
    )

    assert "superuser-only" not in playwright
    assert "separately labeled synthetic-superuser admin path" in playwright
    for required in (
        "def verify_admin_help_and_audit(",
        '"/admin/asklens/asklensquery/"',
        '"/admin/asklens/semanticqueryrun/"',
        '"show me example queries"',
        '"PASS separate admin help and view-only metadata audit"',
        'name="Access unavailable"',
    ):
        assert required in playwright


def test_u6_frontend_explanations_and_demo_recovery_stay_bounded() -> None:
    """U6 explains trusted metadata without changing execution or denial policy."""

    frontend = read_text(FRONTEND_TEMPLATE)
    demo_view = read_text(DEMO_VIEW)
    denial = read_text(DEMO_DENIAL_TEMPLATE)
    demo_guide = read_text(ROOT / "docs" / "test-project-demo.md")
    playwright = read_text(PLAYWRIGHT_TEST)

    for required in (
        "This context is supplied by the server.",
        "Current authorization and row scope are rechecked for every execution",
        "these labels do not grant access",
        "result.result_metadata",
        "Limit:",
        "Truncated:",
        "Truncation applies only to this current authorized query.",
        "A yes value means additional matching rows or groups were detected",
        "Raw response",
        "audit_privacy_notice",
    ):
        assert required in frontend

    for required in (
        "get_demo_audit_privacy_notice",
        'get_asklens_setting("AUDIT_MODE") == "database"',
        'get_asklens_setting("AUDIT_INCLUDE_CONTENT") is False',
        '"audit_privacy_notice": get_demo_audit_privacy_notice()',
        '"test_project/asklens_demo_denied.html"',
        "status=403",
    ):
        assert required in demo_view

    for required in (
        "Access unavailable",
        "This page is not available for this account.",
        'action="/admin/logout/"',
        "{% csrf_token %}",
        'method="post"',
        "Sign out and switch account",
    ):
        assert required in denial
    for forbidden in (
        "resource",
        "report",
        "grant",
        "permission",
        "membership",
        "tenant",
        "scope",
        "binding",
        "diagnostic",
    ):
        assert forbidden not in denial.lower()

    guide_heading = "## What the reference frontend explains"
    assert guide_heading in demo_guide
    guide_section = demo_guide[
        demo_guide.index(guide_heading) : demo_guide.index(
            "## PostgreSQL 18 reference workflow"
        )
    ]
    normalized_guide = " ".join(guide_section.split())
    for required in (
        "server-supplied context labels are not authority",
        "rechecked for every execution",
        "current authorized query",
        "additional matching rows or groups",
        "does not provide pagination",
        "metadata-only database audit",
        "AUDIT_INCLUDE_CONTENT=False",
        "question, complete plan, and result rows are omitted",
        "Raw response remains available",
        "API envelopes and trusted execution payloads are unchanged",
    ):
        assert required in normalized_guide

    for required in (
        '"Limit: 10 groups"',
        '"Truncated: no"',
        '"Limit: 3 rows"',
        '"Truncated: yes"',
        'name="Access unavailable"',
        'name="Sign out and switch account"',
        "expected_audit_rows=2",
    ):
        assert required in playwright


def test_source_demo_and_candidate_commands_are_documented() -> None:
    """A checkout documents setup, smoke, manual, teardown, and limitations."""

    demo = read_text(ROOT / "docs" / "test-project-demo.md")
    install = read_text(ROOT / "docs" / "installation.md")
    production = read_text(ROOT / "docs" / "production-checklist.md")
    migration = read_text(ROOT / "docs" / "migrating-0.1-to-0.2.md")

    assert "uv run playwright install chromium" in demo
    assert "bash scripts/reference-demo-smoke.sh" in demo
    assert "bash scripts/reference-demo-smoke.sh --manual" in demo
    assert "bash scripts/reference-demo-smoke.sh --teardown" in demo
    assert "bash scripts/performance-baseline.sh" in demo
    assert "bash scripts/performance-baseline.sh \\" in demo
    assert "--query-profile compact" in demo
    assert "--dataset-profile" in demo
    assert "Synthetic performance baseline" in demo
    assert "PostgreSQL 18" in demo
    assert "synthetic reference app" in demo
    assert "not production" in demo
    assert "backend-neutral" in demo
    assert "alpha-candidate" in demo
    assert "alpha-candidate-package-smoke.sh" in install
    assert "published 0.1.0a1" in install
    assert "statement timeout" in production.lower()
    assert "request timeout" in production.lower()
    assert "rate" in production.lower()
    assert "concurrency" in production.lower()
    assert "read-only" in production.lower()
    assert "retention" in production.lower()
    assert "redaction" in production.lower()
    assert "deletion" in production.lower()
    assert "strict replacement" in migration.lower()


def test_performance_baseline_guide_and_index_linked() -> None:
    """Synthetic performance baseline docs are isolated and output-safe."""

    guide = read_text(PERFORMANCE_GUIDE)
    index = read_text(ROOT / "docs" / "index.md")
    usage = read_text(ROOT / "docs" / "usage.md")
    ignore = read_text(ROOT / ".gitignore")

    assert "# Synthetic query performance baseline" in guide
    assert "redacted" in guide.lower()
    assert (
        "Runs only against the test-project fixtures and seeded synthetic data."
        in guide
    )
    assert "PostgreSQL 18" in guide
    assert "--query-profile" in guide
    assert "--iterations" in guide
    assert "--warmups" in guide
    assert ".asklens-performance-baseline/" in ignore
    assert "performance-baseline.md" in index
    assert "Synthetic performance baseline" in usage.replace("\n", " ")


def test_private_candidate_guide_is_linked_provenanced_and_privacy_bounded() -> None:
    """Private evaluation uses exact artifacts without release or data claims."""

    guide = read_text(PRIVATE_EVALUATION_GUIDE)
    install = read_text(ROOT / "docs" / "installation.md")
    index = read_text(ROOT / "docs" / "index.md")
    workflow = read_text(ROOT / ".github" / "workflows" / "ci.yml")

    assert "(private-candidate-evaluation.md)" in install
    assert "(private-candidate-evaluation.md)" in index
    assert "(pilot-intake-worksheet.md)" in install
    assert "(pilot-intake-worksheet.md)" in index
    assert "(pilot-intake-worksheet.md)" in guide
    assert '"/docs/private-candidate-evaluation.md"' in workflow
    assert '"/docs/pilot-intake-worksheet.md"' in workflow
    for required in (
        "maintainer-supplied candidate manifest",
        "ASKLENS_CANDIDATE_COMMIT",
        "ASKLENS_CANDIDATE_WHEEL",
        "ASKLENS_CANDIDATE_SHA256",
        "hmac.compare_digest",
        "participant-owned, isolated staging",
        "broad compatibility matrix",
        "PostgreSQL 15 and 18",
        "PG15 is tested with Py3.12/Django 5.2 and Py3.13/Django 6.0",
        "PG18 is tested with Py3.13/Django 6.1",
        "python3 -m venv .venv-asklens-evaluation",
        "${ASKLENS_CANDIDATE_WHEEL}[api]",
        "${ASKLENS_CANDIDATE_WHEEL}[mcp]",
        "python manage.py migrate --plan",
        "python manage.py migrate",
        "python manage.py check",
        '"LLM_BACKEND": "dummy"',
        '"AUDIT_INCLUDE_CONTENT": False',
        "statement timeout",
        "request timeout",
        "rate limits",
        "read only",
        "time to first correctly scoped query",
        "completed evaluation forms and evidence outside this repository",
        "Never put them in candidate manifests, portable fixtures, intake templates",
        "Report suspected security vulnerabilities",
    ):
        assert required in guide

    assert "It is not a normal `0.1.0a1` to `0.2.0a*` upgrade" in guide
    assert "pip install django-asklens==0.2" not in guide
    assert "python3.12 -m venv" not in guide
    assert "twine upload" not in guide
    assert '"AUDIT_INCLUDE_CONTENT": True' not in guide
    assert '"MCP_ALLOW_ROW_RETURN": True' not in guide


def test_pilot_intake_worksheet_is_privacy_bounded() -> None:
    """The intake worksheet strictly forbids exposing sensitive integration details."""

    worksheet = read_text(PILOT_INTAKE_WORKSHEET).lower()

    for required in (
        "participant class",
        "python version",
        "django version",
        "database engine",
        "primary asklens surface",
        "semantic fields",
        "semantic metrics",
        "scope mode",
        "timezone configuration",
        "role/membership condition",
        "tenant isolation",
        "allowed expectations",
        "denial expectations",
        "intent/mode",
        "expected status",
        "expected shape/count",
        "cross-scope",
        "hidden/filter-only/result-excluded/unknown member",
        "client-supplied policy claims",
        "missing context",
        "structural budget",
        "mcp row-return",
        "provider metadata boundary",
        "audit policy mode",
        "storage owner",
        "retention & deletion",
        "prohibited artifacts",
        "provider/client planning mode",
        "initial smoke test",
        "time to integration",
        "time to first correctly scoped query",
        "maintainer intervention",
        "registration effort",
        "baseline custom-report",
        "asklens.member.unavailable",
        "asklens.budget.exceeded",
        "a correctly scoped application-data query may execute",
        "no out-of-scope rows or aggregate influence",
        "returned query data/rows are omitted unless host+request opt in",
        "inspect the permission-scoped catalog and pre-provider request",
        "truncation applies only within an accepted limit",
        "omission is not a query-cost control",
        "never include:** participant names, application names",
        "exact schema/model/binding paths",
        "database rows or sample values",
        "questions containing private facts",
        "tenant or user identifiers",
        "permission strings, credentials, secrets, `.env` files",
        "scope-provider code",
        "full sensitive plan or filter values",
        "provider payloads, provider logs, or full audit content",
    ):
        assert required in worksheet

    for forbidden in (
        "zero cross-tenant sql",
        "asklens.parse.invalid or exact observed stable code",
        "metadata/aggregate only; zero row exposure",
        "passing a payload containing orm binding details",
        "rejection or truncation depending on limit policy",
        "provider adapter drops private bindings",
        "local isolated sqlite",
    ):
        assert forbidden not in worksheet, f"Forbidden phrase found: {forbidden}"


def _extract_alias_block(settings_text: str, alias: str) -> str:
    """Return the raw text for one configured database alias block."""

    marker = f'"{alias}": {{'
    start = settings_text.find(marker)
    if start < 0:
        raise AssertionError(f"Database alias '{alias}' block not found")
    open_braces = 0
    # Track braces from the start of the alias block.
    for index in range(start, len(settings_text)):
        if settings_text[index] == "{":
            open_braces += 1
        elif settings_text[index] == "}":
            open_braces -= 1
            if open_braces == 0:
                return settings_text[start : index + 1]
    raise AssertionError(f"Could not parse alias block for '{alias}'")


def test_host_throttle_and_audit_controls_guide_is_assertive() -> None:
    """Host operations guidance includes explicit throttle and sink-control
    guardrails.
    """

    guide = read_text(ROOT / "docs" / "host-throttle-and-audit-controls.md")
    production = read_text(ROOT / "docs" / "production-checklist.md")
    security = read_text(ROOT / "docs" / "security-checklist.md")
    usage = read_text(ROOT / "docs" / "usage.md")

    assert "Host throttle, concurrency, and AskLens observability controls" in guide
    assert "UserRateThrottle" in guide
    assert "authenticated principal-bound" in guide
    assert "X-Forwarded-For" in guide
    assert "Do not let spoofed proxy headers choose authenticated identity" in guide
    assert "error_code" in guide
    assert "error_code` may be a stable label" in guide
    assert "free-form `error_message`" in guide
    assert "do not use free-form `error_message` in\nmetric labels" in guide
    assert "trusted-proxy" in guide.lower()
    assert "provider/client output as untrusted" in guide
    assert "validated by" in guide
    assert "AUDIT_MODE" in guide
    assert 'DJANGO_ASKLENS["AUDIT_MODE"] = "custom"' in guide
    assert "does not require OpenTelemetry" in guide
    assert "host-owned" in guide

    assert "Host throttling and audit controls" in production
    assert "Apply authenticated-principal/route rate limits" in production
    assert (
        "Do not treat OpenTelemetry/Prometheus/queue/cache/service dependencies "
        "as required infrastructure" in production
    )

    assert "Host throttling and audit controls" in security
    assert "equivalent host limits" in security

    assert "Host throttling and audit controls" in usage


def test_audit_lifecycle_docs_and_artifacts_cover_irreversible_purge() -> None:
    """Lifecycle docs and installed-wheel guards retain purge safety boundaries."""

    core = read_text(ROOT / "docs" / "core-python-api.md")
    host = read_text(ROOT / "docs" / "host-throttle-and-audit-controls.md")
    production = read_text(ROOT / "docs" / "production-checklist.md")
    security = read_text(ROOT / "docs" / "security-checklist.md")
    changelog = read_text(ROOT / "CHANGELOG.md")
    wheel_smoke = read_text(ROOT / ".github" / "scripts" / "wheel_smoke.py")
    workflow = read_text(ROOT / ".github" / "workflows" / "ci.yml")

    for document in (core, host, production, security, changelog):
        assert "redact_asklens_audit" in document
        assert "purge_asklens_audit" in document

    combined_guidance = "\n".join((core, host, production, security)).lower()
    for required in (
        "preview",
        "--execute",
        "irreversible",
        "high-water",
        "higher-pk",
        "manually inserted",
        "reused lower",
        "snapshot guarantee",
        "point-in-time",
        "backup/restore",
        "pre_delete",
        "post_delete",
        "cascade",
        "protect",
        "restrict",
        "external",
        "cannot be rolled back",
        "earlier committed batches",
        "rerun preview",
        "targets",
        "related host rows",
        "custom sink",
        "backups",
        "replicas",
        "no scheduler",
        "automatic retention policy",
        "view-only",
        "including superusers",
        "delete_selected",
        "asklens-provided operator workflows",
        "not universal host authorization or mutation controls",
        "not a complete",
    ):
        assert required in combined_guidance

    normalized_host = host.replace("\n", " ")
    assert "does not schedule this command" not in normalized_host
    assert "does not schedule these commands" in normalized_host

    normalized_guidance = combined_guidance.replace("\n", " ")
    for inaccurate in (
        "act only on the selected built-in database table",
        "acts only on the selected built-in database table",
        "operate only on the selected built-in database table",
        "operates only on the selected built-in database table",
        "both commands act on selected built-in database rows",
        "existing django admin deletion continues to follow normal model permissions",
        "existing django admin mutation remains governed by normal model permissions",
        "existing audit-admin mutation continues to use normal django model "
        "permissions",
        "command-only admin hardening",
    ):
        assert inaccurate not in normalized_guidance
    assert 'commands["purge_asklens_audit"] == "django_asklens"' in wheel_smoke
    assert '"django_asklens/management/commands/purge_asklens_audit.py"' in workflow


def test_test_settings_include_read_alias_for_routing_evidence() -> None:
    """SQLite and PostgreSQL test settings re-use a mirrored `asklens_read` alias."""

    sqlite_settings = read_text(ROOT / "tests" / "test_project" / "settings.py")
    pg_settings = read_text(ROOT / "tests" / "test_project" / "postgresql_settings.py")

    for settings_text in (sqlite_settings, pg_settings):
        assert '"asklens_read"' in settings_text
        alias_block = _extract_alias_block(settings_text, "asklens_read")
        assert '"TEST": {' in alias_block
        assert '"MIRROR": "default"' in alias_block
