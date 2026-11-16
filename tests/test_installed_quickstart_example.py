"""Source-level consumer-app regressions, not installed-wheel conformance proof.

The copied example runs against source in this pytest check. Issue #185 covers
an automated exact-wheel tutorial harness; #184 also records a manual run with
an authenticated public artifact outside the checkout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "quickstart"


def test_minimal_consumer_behaviour_in_disposable_project(tmp_path: Path) -> None:
    project = tmp_path / "consumer"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "db.sqlite3", ".venv"),
    )
    # Explicit source-level regression only. The public consumer instructions
    # must not set PYTHONPATH and are verified separately with an installed wheel.
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(ROOT),
        "DJANGO_SETTINGS_MODULE": "quickstart.settings",
    }
    completed = subprocess.run(
        [sys.executable, "manage.py", "test", "shop", "--verbosity", "1"],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Ran 9 tests" in completed.stderr
    assert not (project / "db.sqlite3").exists()


@pytest.mark.parametrize(
    ("case", "configuration", "expected_status"),
    [
        ("unmigrated", "", "OK"),
        (
            "invalid-audit-mode",
            'DJANGO_ASKLENS = {**DJANGO_ASKLENS, "AUDIT_MODE": "invalid"}\n',
            "OK",
        ),
        (
            "missing-registration",
            "INSTALLED_APPS = [app for app in INSTALLED_APPS "
            'if not app.startswith("shop")]\n',
            "EMPTY",
        ),
        (
            "duplicate-registration",
            "INSTALLED_APPS = [\n"
            '    "duplicate_app.DuplicateConfig" if app.startswith("shop") else app\n'
            "    for app in INSTALLED_APPS\n]\n",
            None,
        ),
        (
            "invalid-declaration",
            "INSTALLED_APPS = [\n"
            '    "invalid_app.InvalidConfig" if app.startswith("shop") else app\n'
            "    for app in INSTALLED_APPS\n]\n",
            None,
        ),
        (
            "cached-import",
            "INSTALLED_APPS = [\n"
            '    "cached_app.CachedConfig" if app.startswith("shop") else app\n'
            "    for app in INSTALLED_APPS\n]\n",
            "OK",
        ),
    ],
)
def test_existing_setup_checks_have_distinct_limits(
    tmp_path: Path, case: str, configuration: str, expected_status: str | None
) -> None:
    """Reproduce startup/readiness gaps using the real app, not a new installer."""

    project = tmp_path / "consumer"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "db.sqlite3", ".venv"),
    )
    (project / "diagnostic_settings.py").write_text(
        "from quickstart.settings import *\n" + configuration, encoding="utf-8"
    )
    if case == "duplicate-registration":
        (project / "duplicate_app.py").write_text(
            "from shop.apps import ShopConfig\n"
            "class DuplicateConfig(ShopConfig):\n"
            "    def ready(self):\n"
            "        super().ready()\n"
            "        import runpy\n"
            '        runpy.run_module("shop.asklens_registration")\n',
            encoding="utf-8",
        )
    elif case == "invalid-declaration":
        (project / "invalid_app.py").write_text(
            "from shop.apps import ShopConfig\n"
            "class InvalidConfig(ShopConfig):\n"
            "    def ready(self):\n"
            "        super().ready()\n"
            "        from django_asklens import register\n"
            "        from shop.asklens_registration import visible_orders\n"
            "        from shop.models import Order\n"
            "        register(\n"
            "            model=Order, name='invalid', timezone='UTC',\n"
            "            scope_mode='context_scoped', scope_provider=visible_orders,\n"
            "            fields={'status': {'type': 'string', 'nullable': False}})\n",
            encoding="utf-8",
        )
    elif case == "cached-import":
        (project / "cached_app.py").write_text(
            "from shop.apps import ShopConfig\n"
            "class CachedConfig(ShopConfig):\n"
            "    def ready(self):\n"
            "        super().ready()\n"
            "        import importlib\n"
            "        importlib.import_module('shop.asklens_registration')\n",
            encoding="utf-8",
        )

    def run(command: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "manage.py",
                command,
                *args,
                "--settings=diagnostic_settings",
            ],
            cwd=project,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT)},
            text=True,
            capture_output=True,
            timeout=30,
        )

    summary = run("check_asklens", "--fail-on-empty")
    if expected_status is None:
        assert summary.returncode != 0
        expected_error = (
            "InvalidResourceError"
            if case == "invalid-declaration"
            else "DuplicateResourceError"
        )
        assert expected_error in summary.stderr
        assert "AskLens registry summary" not in summary.stdout
        return

    assert summary.returncode == (1 if expected_status == "EMPTY" else 0)
    assert f"Status: {expected_status}\n" in summary.stdout
    assert run("check").returncode == 0
    # Django/system and registry checks can both be green on an unmigrated DB.
    assert run("migrate", "--check").returncode != 0


@pytest.mark.parametrize(
    ("module", "settings"),
    [
        ("admin_recipe", "web_settings"),
        ("api_recipe", "api_settings"),
        ("mcp_recipe", "mcp_settings"),
    ],
)
def test_opt_in_adapter_recipes_in_disposable_project(tmp_path, module, settings):
    project = tmp_path / "consumer"
    shutil.copytree(
        EXAMPLE, project, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    result = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "test",
            f"shop.{module}",
            f"--settings=quickstart.{settings}",
            "--verbosity",
            "1",
        ],
        cwd=project,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT)},
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (project / "db.sqlite3").exists()


def test_consumer_source_has_no_test_project_or_optional_imports() -> None:
    import ast

    forbidden = {"tests", "rest_framework", "fastmcp"}
    for path in EXAMPLE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any(name.split(".")[0] in forbidden for name in names), path


def test_consumer_guide_is_discoverable_and_preserves_provenance() -> None:
    guide = (ROOT / "docs" / "quickstart-app.md").read_text(encoding="utf-8")
    for path, link in (
        (ROOT / "README.md", "docs/quickstart-app.md"),
        (ROOT / "docs/index.md", "quickstart-app.md"),
        (ROOT / "docs/quickstart-core.md", "quickstart-app.md"),
        (ROOT / "mkdocs.yml", "quickstart-app.md"),
    ):
        assert link in path.read_text(encoding="utf-8")
    for required in (
        "Show my paid orders",
        "Show my refunded orders",
        "--as-user no-report",
        "seed_quickstart",
        "AppConfig.ready()",
        "scope_provider",
        "request.user",
        "739d5411cd0b0ab63ac8dae9e9a0a4f2cf396cb2e0f0ef5bbfac9a2c4607b050",
        "e522055e3b34eac434cabff6db8bb4c278e210591bcd95027956f2449daee177",
        "not arbitrary natural language",
        "alpha",
        "synthetic",
        "#185",
    ):
        assert required in guide
    assert "PYTHONPATH=" not in guide


def test_shared_troubleshooting_is_linked_from_integration_entry_points() -> None:
    for path in (
        "mkdocs.yml",
        "docs/quickstart-app.md",
        "docs/usage.md",
        "docs/providers.md",
        "docs/custom-ui.md",
    ):
        assert "troubleshooting.md" in (ROOT / path).read_text(encoding="utf-8")
