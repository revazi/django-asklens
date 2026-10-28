"""Keep public 0.3.2 status and historical preparation evidence distinct."""

from __future__ import annotations

import ast
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_agrees_across_source_metadata_and_lock() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    module = ast.parse((ROOT / "django_asklens/__init__.py").read_text())
    exported = next(
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        )
    )
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    locked = next(p for p in lock["package"] if p["name"] == "django-asklens")
    assert metadata["project"]["version"] == exported == locked["version"] == "0.3.2"
    assert metadata["project"]["urls"]["Documentation"] == (
        "https://revazi.github.io/django-asklens/"
    )


def test_release_closeout_records_public_identity_and_preserves_history() -> None:
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "`django-asklens==0.3.2` is the current published alpha" in readme
    assert "`0.3.1` remains current" not in readme
    assert "python -m pip install 'django-asklens==0.3.2'" in readme
    assert "https://revazi.github.io/django-asklens/" in readme

    index = " ".join((ROOT / "docs/index.md").read_text().split())
    assert "`django-asklens==0.3.2` is the current published alpha" in index
    assert "PyPI version record" in index

    mkdocs = (ROOT / "mkdocs.yml").read_text()
    assert "0.3.2 release preparation record" in mkdocs
    assert "Proposed 0.3.2 preparation" not in mkdocs

    preparation = " ".join(
        (ROOT / "docs/release-preparation-0.3.2.md").read_text().split()
    )
    assert "Status: published 2026-10-27" in preparation
    assert "preserve the pre-publication candidate rationale" in preparation

    release_notes = " ".join(
        (ROOT / ".github/release-notes/0.3.2.md").read_text().split()
    )
    assert "not publication authorization or proof of publication" in release_notes
    assert "Before a successful Trusted Publishing run" in release_notes
    assert "After publication" in release_notes
    assert "immutable `v0.3.2` GitHub Release" in release_notes

    changelog = (ROOT / "CHANGELOG.md").read_text()
    released = changelog.split("## 0.3.2 — 2026-10-27", 1)[1].split("## 0.3.1", 1)[0]
    assert "current published alpha" in released
    assert "No AskLens migration" in released

    install = (ROOT / "docs/installation.md").read_text()
    assert "## Current published alpha: 0.3.2" in install
    for identity in (
        "5ab7e9e76f6a39a59894ae2fce600e4c707077c3",
        "b3cb5a5b84fdeb35f1b4ce972a0abd33b6934982",
        "9fba0b64b5f4efc5ae15cc9790374d3528acc1af",
        "739d5411cd0b0ab63ac8dae9e9a0a4f2cf396cb2e0f0ef5bbfac9a2c4607b050",
        "e522055e3b34eac434cabff6db8bb4c278e210591bcd95027956f2449daee177",
    ):
        assert identity in install
    assert "Do not install `0.3.2` from PyPI" not in install


def test_all_upgrade_origins_are_explicit_and_authenticated() -> None:
    script = (ROOT / "scripts/alpha-candidate-package-smoke.sh").read_text()
    for version, digest in (
        ("0.3.1", "4332c62aad6e7b27f553af3f8796ed6090e6207ddad6a30a1c4665e9a1085887"),
        ("0.3.0", "d7f7159cfdbb3d9755d9b3542f9cda4280f0e72939f81aca4d3a2cd8d8921e8b"),
        ("0.2.0", "af0881945d5f5f227332aac8bb13df10d4cf5bd3e54a038acd6545db5640d1d8"),
    ):
        assert f"--version {version}" in script
        assert digest in script
        assert f'  {version} "$public_' in script
    assert "Public 0.3.1 is the immediate maintenance origin" in script
    assert "Refusing to build package evidence from a dirty source tree" in script
    assert "django_asklens-0.3.2-py3-none-any.whl" in script
    assert "no publication was performed" in script
    subprocess.run(
        ["bash", "-n", "scripts/alpha-candidate-package-smoke.sh"], cwd=ROOT, check=True
    )


def test_release_retains_runtime_bounds_and_migrations() -> None:
    """Closeout retains the released support surface and migration graph."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["requires-python"] == ">=3.12"
    assert project["dependencies"] == ["Django>=5.2,<7.0", "pydantic>=2,<3"]
    assert project["optional-dependencies"] == {
        "api": ["djangorestframework>=3.18,<4.0"],
        "mcp": ["fastmcp>=3.4,<5"],
    }
    assert "Development Status :: 3 - Alpha" in project["classifiers"]
    assert sorted(
        p.name for p in (ROOT / "django_asklens/migrations").glob("*.py")
    ) == ["0001_initial.py", "0002_add_admin_query_proxy.py", "__init__.py"]
