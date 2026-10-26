"""Keep unpublished 0.3.2 preparation distinct from immutable public 0.3.1."""

from __future__ import annotations

import ast
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_candidate_version_agrees_across_source_metadata_and_lock() -> None:
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
        "https://github.com/revazi/django-asklens/tree/main/docs"
    )


def test_candidate_docs_do_not_claim_a_public_release() -> None:
    for name in (
        "README.md",
        "docs/index.md",
        "docs/release-preparation-0.3.2.md",
    ):
        text = (ROOT / name).read_text()
        assert "unpublished" in text.lower(), name
        assert "0.3.1" in text and "0.3.2" in text, name
    release_notes = " ".join(
        (ROOT / ".github/release-notes/0.3.2.md").read_text().split()
    )
    assert "not publication authorization or proof of publication" in release_notes
    assert "Before a successful Trusted Publishing run" in release_notes
    assert "After publication" in release_notes
    assert "immutable `v0.3.2` GitHub Release" in release_notes
    changelog = (ROOT / "CHANGELOG.md").read_text()
    candidate = changelog.split("## 0.3.2 — Unpublished candidate", 1)[1].split(
        "## 0.3.1", 1
    )[0]
    assert "Public `0.3.1` remains current" in candidate
    assert "No AskLens migration" in candidate
    install = (ROOT / "docs/installation.md").read_text()
    assert "## Current published alpha: 0.3.1" in install
    assert "Do not install `0.3.2` from PyPI" in install


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


def test_candidate_does_not_change_runtime_bounds_or_migrations() -> None:
    """Preparation retains the current source baseline's declared support surface."""
    # Explicit invariants also work in shallow checkouts and exported source.
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
