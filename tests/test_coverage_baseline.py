"""Regression checks for the informational branch-coverage baseline."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "pyproject.toml"
LOCK = ROOT / "uv.lock"
SCRIPT = ROOT / "scripts" / "coverage-baseline.sh"
GUIDE = ROOT / "docs" / "test-coverage.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def read_text(path: Path) -> str:
    """Return a repository artifact as UTF-8 text."""

    return path.read_text(encoding="utf-8")


def test_coverage_tool_is_dev_only_branch_aware_and_has_no_threshold() -> None:
    """Coverage measures the complete package without becoming a percentage gate."""

    project = tomllib.loads(read_text(PROJECT))
    lock = tomllib.loads(read_text(LOCK))

    coverage_requirement = "coverage>=7,<8"
    assert coverage_requirement in project["dependency-groups"]["dev"]
    assert all(
        not requirement.lower().startswith("coverage")
        for requirement in project["project"]["dependencies"]
    )
    assert all(
        not requirement.lower().startswith("coverage")
        for requirements in project["project"]["optional-dependencies"].values()
        for requirement in requirements
    )

    run_config = project["tool"]["coverage"]["run"]
    assert run_config["branch"] is True
    assert run_config["source"] == ["django_asklens"]
    assert run_config["relative_files"] is True

    report_config = project["tool"]["coverage"]["report"]
    assert "omit" not in run_config
    assert "omit" not in report_config
    assert "exclude_lines" not in report_config
    assert "exclude_also" not in report_config
    assert "fail_under" not in report_config

    locked_packages = {package["name"]: package for package in lock["package"]}
    assert "coverage" in locked_packages
    asklens = locked_packages["django-asklens"]
    dev_names = {item["name"] for item in asklens["dev-dependencies"]["dev"]}
    assert "coverage" in dev_names


def test_coverage_runner_is_reproducible_and_ci_visible() -> None:
    """The runner clears stale data and reports an informational CI baseline."""

    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111
    script = read_text(SCRIPT)
    workflow = read_text(WORKFLOW)

    for required in (
        "set -Eeuo pipefail",
        "git rev-parse --verify HEAD",
        "git symbolic-ref --quiet --short HEAD",
        "uv run --no-sync coverage erase",
        "uv run --no-sync coverage run -m pytest --strict-config --strict-markers",
        "uv run --no-sync coverage report",
    ):
        assert required in script
    assert "--fail-under" not in script
    subprocess.run(["bash", "-n", SCRIPT], check=True, cwd=ROOT)

    assert "Run informational branch coverage baseline" in workflow
    assert "bash scripts/coverage-baseline.sh" in workflow
    assert '("coverage", "httpx", "playwright", "psycopg")' in workflow
    assert '"/docs/test-coverage.md"' in workflow
    assert '"/scripts/coverage-baseline.sh"' in workflow
    assert "matrix.python-version == '3.12'" in workflow
    assert "matrix.django-version == '5.2'" in workflow


def test_critical_boundary_map_names_sources_tests_and_limits() -> None:
    """The baseline maps all authorized critical boundaries to focused evidence."""

    assert GUIDE.is_file()
    guide = read_text(GUIDE)
    normalized_guide = " ".join(guide.split())
    index = read_text(ROOT / "docs" / "index.md")
    contributing = read_text(ROOT / "CONTRIBUTING.md")

    for heading in (
        "# Test coverage baseline and critical-boundary map",
        "## Reproduce the baseline",
        "## Recorded baseline",
        "## Critical-boundary map",
        "## Interpretation and limitations",
    ):
        assert heading in guide

    for boundary in (
        "Trusted execution facade",
        "Optional API adapter",
        "Optional MCP adapter",
        "Admin and frontend adapters",
        "Fail-closed scope",
        "Structural budgets",
        "Private bindings and compilation",
        "Result serialization",
        "Audit privacy and lifecycle",
    ):
        assert boundary in guide

    for source_path in (
        "../django_asklens/execution/runner.py",
        "../django_asklens/api/views.py",
        "../django_asklens/mcp/core.py",
        "../django_asklens/admin_querying.py",
        "../django_asklens/catalog/registry.py",
        "../django_asklens/planning/validation.py",
        "../django_asklens/compiler/orm.py",
        "../django_asklens/results/serialization.py",
        "../django_asklens/execution/audit.py",
    ):
        assert source_path in guide

    for test_path in (
        "../tests/execution/test_facade.py",
        "../tests/api/test_http_characterization.py",
        "../tests/mcp/test_core.py",
        "../tests/test_admin_access.py",
        "../tests/catalog/test_scope_policy.py",
        "../tests/planning/test_budgets.py",
        "../tests/compiler/test_orm.py",
        "../tests/results/test_serialization.py",
        "../tests/execution/test_audit_boundary.py",
    ):
        assert test_path in guide

    for limitation in (
        "no percentage threshold",
        "SQLite",
        "PostgreSQL",
        "live provider",
        "browser",
        "installed-wheel",
        "independent security audit",
    ):
        assert limitation in normalized_guide

    coverage_link = (
        "[Test coverage baseline and critical-boundary map](test-coverage.md)"
    )
    assert coverage_link in index
    assert "bash scripts/coverage-baseline.sh" in contributing
