"""Offline checks for the opt-in PostgreSQL reference-demo evidence."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "compose.yaml"
REFERENCE_SCRIPT = ROOT / "scripts" / "reference-demo-smoke.sh"
PACKAGE_SCRIPT = ROOT / "scripts" / "alpha-candidate-package-smoke.sh"
PLAYWRIGHT_TEST = ROOT / "tests" / "e2e" / "reference_demo.py"
PRIVATE_EVALUATION_GUIDE = ROOT / "docs" / "private-candidate-evaluation.md"
PILOT_INTAKE_WORKSHEET = ROOT / "docs" / "pilot-intake-worksheet.md"
PERFORMANCE_SCRIPT = ROOT / "scripts" / "performance-baseline.sh"
PERFORMANCE_GUIDE = ROOT / "docs" / "performance-baseline.md"


def read_text(path: Path) -> str:
    """Return one committed source artifact as UTF-8 text."""

    return path.read_text(encoding="utf-8")


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


def test_dev_tools_do_not_leak_into_runtime_metadata() -> None:
    """Docker, PostgreSQL, and Playwright remain source/dev-only tools."""

    metadata = tomllib.loads(read_text(ROOT / "pyproject.toml"))
    runtime = "\n".join(metadata["project"]["dependencies"]).lower()
    extras = "\n".join(
        dependency
        for requirements in metadata["project"]["optional-dependencies"].values()
        for dependency in requirements
    ).lower()

    for forbidden in ("docker", "playwright", "psycopg"):
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
            '            django-package: "Django>=5.2,<6.0"'
        ),
        (
            '- postgresql-version: "15"\n'
            '            python-version: "3.13"\n'
            '            django-version: "6.x"\n'
            '            django-package: "Django>=6.0,<7.0"'
        ),
        (
            '- postgresql-version: "18"\n'
            '            python-version: "3.13"\n'
            '            django-version: "6.x"\n'
            '            django-package: "Django>=6.0,<7.0"'
        ),
    ]
    for expected in expected_tuples:
        assert expected in include

    # Assert parameterized setup and install steps.
    assert "python-version: ${{ matrix.python-version }}" in job
    assert 'uv pip install --reinstall "${{ matrix.django-package }}"' in job

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
        "PG15 is tested with Py3.12/Django 5.2 and Py3.13/Django 6.x",
        "PG18 is tested with Py3.13/Django 6.x",
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
