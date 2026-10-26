"""Regression checks for the local showcase, static docs, and draft packets."""

from __future__ import annotations

import importlib.util
import re
import struct
import tomllib
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets" / "showcase"


def load_module(name: str, path: Path) -> ModuleType:
    """Load a repository script without requiring it to be a package."""

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def png_dimensions(path: Path) -> tuple[int, int]:
    """Read dimensions from a PNG IHDR without an image-library dependency."""

    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def test_browser_showcase_assets_are_real_and_bounded() -> None:
    """Committed captures remain browser-sized and reasonable for repository docs."""

    for name in ("scoped-revenue.png", "neutral-denial.png"):
        path = ASSETS / name
        assert path.is_file()
        width, height = png_dimensions(path)
        assert width == 1440
        assert 900 <= height <= 3_000
        assert 10_000 < path.stat().st_size < 1_500_000

    video = ASSETS / "offline-demo.webm"
    assert video.is_file()
    assert video.read_bytes()[:4] == b"\x1aE\xdf\xa3"
    assert 25_000 < video.stat().st_size < 8_000_000

    captions = (ASSETS / "offline-demo.vtt").read_text(encoding="utf-8")
    assert captions.startswith("WEBVTT\n")
    assert "North Studio" in captions
    assert "No matching rows" in captions


def test_showcase_has_reproducible_offline_capture_and_accessible_context() -> None:
    """README/docs identify exact questions, scope, provenance, and capture command."""

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    showcase = (ROOT / "docs" / "showcase.md").read_text(encoding="utf-8")
    capture = (ROOT / "scripts" / "capture-showcase.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts" / "capture-showcase.sh").read_text(encoding="utf-8")

    for text in (readme, showcase):
        assert "Show paid billing revenue by product" in text
        assert "North Studio" in text
        assert "offline" in text.lower()
        assert "arbitrary" in text.lower()
        assert "0.3.1" in text
    assert "![" in showcase
    assert 'kind="captions"' in showcase
    assert 'aria-describedby="offline-walkthrough"' in showcase
    assert "The recording has no narration" in showcase
    assert "bash scripts/capture-showcase.sh" in showcase
    assert "record_video_dir" in capture
    assert "verify_unmatched_question_error" in capture
    assert "DJANGO_ASKLENS_DEMO_LIVE_LLM=0" in wrapper
    assert "Refusing to replace existing synthetic demo database" in wrapper


def test_docs_tooling_is_isolated_and_pages_workflows_are_build_only() -> None:
    """Docs dependencies stay out of runtime and workflows cannot deploy."""

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["dependency-groups"]["docs"] == ["mkdocs==1.6.1"]
    assert all(
        not requirement.lower().startswith("mkdocs")
        for requirement in metadata["project"]["dependencies"]
    )

    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "exclude_docs:" in config
    for excluded in ("outreach/", "mkdocs_hooks.py", "__pycache__/"):
        assert excluded in config
    assert "site/" in (ROOT / ".gitignore").read_text(encoding="utf-8")

    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "prune docs/assets" in manifest
    assert "prune docs/outreach" in manifest
    assert "exclude mkdocs.yml" in manifest
    assert "exclude docs/mkdocs_hooks.py" in manifest
    assert "exclude scripts/capture-showcase.py" in manifest
    assert "exclude scripts/verify-docs-site.py" in manifest

    for page in (
        "quickstart-core.md",
        "registration.md",
        "providers.md",
        "security-checklist.md",
        "custom-ui.md",
        "mcp-integration.md",
    ):
        assert page in config

    workflow = (ROOT / ".github" / "workflows" / "docs-pages.yml").read_text(
        encoding="utf-8"
    )
    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "github.ref_name == github.event.repository.default_branch" in workflow
    assert "Prepare documentation for Pages (no deployment)" in workflow

    build_only = (ROOT / ".github" / "workflows" / "docs.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request:" in build_only
    assert "Build and validate (no deployment)" in build_only

    for candidate in (workflow, build_only):
        assert "contents: read" in candidate
        assert "pages: write" not in candidate
        assert "id-token: write" not in candidate
        assert "upload-pages-artifact" not in candidate
        assert "deploy-pages" not in candidate
        assert "environment:" not in candidate
        assert "pypi" not in candidate.lower()

    activation = (ROOT / "docs" / "pages-deployment.md").read_text(encoding="utf-8")
    assert "No workflow in this documentation slice can deploy the site" in activation
    assert "separate, authorized pull" in activation


def test_docs_hook_rewrites_build_only_markup_behaviorally() -> None:
    """The hook adapts source-friendly callouts, links, and showcase media."""

    hook = load_module("mkdocs_hooks", ROOT / "docs" / "mkdocs_hooks.py")
    page = SimpleNamespace(file=SimpleNamespace(src_path="showcase.md"))
    remote = (
        "https://raw.githubusercontent.com/revazi/django-asklens/"
        "main/docs/assets/showcase/"
    )
    markdown = (
        "> [!IMPORTANT]\n> Keep this boundary.\n\n"
        "[Source](../README.md)\n"
        f"![Result]({remote}scoped-revenue.png)\n"
        f'<video poster="{remote}scoped-revenue.png">'
        f'<track src="{remote}offline-demo.vtt"></video>'
    )
    rendered = hook.on_page_markdown(markdown, page=page)
    assert '!!! important "Important"' in rendered
    assert "github.com/revazi/django-asklens/blob/main/README.md" in rendered
    assert "![Result](assets/showcase/scoped-revenue.png)" in rendered
    assert 'poster="../assets/showcase/scoped-revenue.png"' in rendered
    assert 'src="../assets/showcase/offline-demo.vtt"' in rendered
    assert "raw.githubusercontent.com" not in rendered


def test_sdist_excluded_showcase_assets_are_not_relative_doc_dependencies() -> None:
    """Pruned media are not relative dependencies of Markdown shipped in sdist."""

    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "prune docs/assets" in manifest
    markdown_paths = (
        ROOT / "README.md",
        ROOT / "docs/index.md",
        ROOT / "docs/showcase.md",
    )
    relative_media = re.compile(
        r'(?:\]\(|(?:src|href|poster)=")'
        r"(?:docs/)?assets/showcase/[^)\"\s]+"
    )
    for path in markdown_paths:
        assert relative_media.search(path.read_text(encoding="utf-8")) is None, path

    showcase = (ROOT / "docs/showcase.md").read_text(encoding="utf-8")
    assert "full Git checkout" in showcase
    assert "not\nincluded in Python source distributions" in showcase


def test_rendered_site_validator_rejects_internal_artifacts(tmp_path: Path) -> None:
    """Drafts, hooks, and bytecode fail validation if a build copies them."""

    validator = load_module(
        "verify_docs_site", ROOT / "scripts" / "verify-docs-site.py"
    )
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "outreach").mkdir()
    (tmp_path / "outreach" / "draft.html").write_text("draft", encoding="utf-8")
    (tmp_path / "mkdocs_hooks.py").write_text("# leaked", encoding="utf-8")
    failures, _page_count = validator.validate_site(tmp_path)
    assert any("outreach/draft.html" in failure for failure in failures)
    assert any("mkdocs_hooks.py" in failure for failure in failures)


def test_outreach_packets_are_drafts_with_observed_limits() -> None:
    """External-action packets remain factual drafts rather than adoption claims."""

    outreach = ROOT / "docs" / "outreach"
    forum = (outreach / "django-forum-show-and-tell-draft.md").read_text(
        encoding="utf-8"
    )
    news = (outreach / "django-news-draft.md").read_text(encoding="utf-8")
    packages = (outreach / "django-packages-observation.md").read_text(encoding="utf-8")
    awesome = (outreach / "awesome-django-submission-packet.md").read_text(
        encoding="utf-8"
    )

    for draft in (forum, news):
        assert "AI assistance" in draft
        assert "author" in draft.lower()
        assert "feedback" in draft.lower()
        assert "alpha" in draft.lower()
    assert "without logging in" in packages
    assert re.search(r"\*\*Observed:\*\* 20\d{2}-\d{2}-\d{2} UTC", packages)
    assert "pages 1 and 2" in packages
    assert "Neither returned page contained" in packages
    assert "not ready to submit" in awesome.lower()
    assert "under 100 stars" in awesome
    assert "- [x] Yes" in awesome
    assert "- [x] No, it is free and open source" in awesome
