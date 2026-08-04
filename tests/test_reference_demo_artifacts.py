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
