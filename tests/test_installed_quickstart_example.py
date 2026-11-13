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
    assert "Ran 8 tests" in completed.stderr
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
