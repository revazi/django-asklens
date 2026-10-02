from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_HELPER = ROOT / "scripts/download_pypi_artifacts.py"
PUBLISH_WORKFLOW = ROOT / ".github/workflows/publish.yml"


def load_download_helper():
    spec = importlib.util.spec_from_file_location(
        "download_pypi_artifacts", DOWNLOAD_HELPER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def release_document(version: str = "0.2.0") -> dict:
    return {
        "info": {"name": "django-asklens", "version": version},
        "urls": [
            {
                "filename": f"django_asklens-{version}-py3-none-any.whl",
                "packagetype": "bdist_wheel",
                "yanked": False,
            },
            {
                "filename": f"django_asklens-{version}.tar.gz",
                "packagetype": "sdist",
                "yanked": False,
            },
        ],
    }


def test_pypi_selector_requires_exact_release_artifact_set():
    helper = load_download_helper()

    selected = helper.select_artifacts(release_document(), "0.2.0")

    assert set(selected) == {"bdist_wheel", "sdist"}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda document: document["info"].update(version="0.2.1"),
        lambda document: document["urls"].pop(),
        lambda document: document["urls"][0].update(yanked=True),
        lambda document: document["urls"][0].update(filename="other.whl"),
        lambda document: document["urls"].append(document["urls"][0].copy()),
    ],
)
def test_pypi_selector_rejects_ambiguous_or_mismatched_metadata(mutation):
    helper = load_download_helper()
    document = release_document()
    mutation(document)

    with pytest.raises(SystemExit):
        helper.select_artifacts(document, "0.2.0")


def test_publish_workflow_limits_oidc_to_protected_publish_job():
    workflow = PUBLISH_WORKFLOW.read_text()

    assert "release:\n    types: [published]" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert workflow.count("id-token: write") == 1
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "password:" not in workflow
    assert "user:" not in workflow
    assert "skip-existing:" not in workflow
    assert "ref: ${{ github.event.release.tag_name }}" in workflow
    assert 'test "$RELEASE_TAG" = "v$version"' in workflow


def test_post_publication_verification_uses_build_digests_and_supported_matrix():
    workflow = PUBLISH_WORKFLOW.read_text()

    assert "needs: [build, publish]" in workflow
    assert "scripts/published-package-smoke.sh" in workflow
    assert "needs.build.outputs.wheel_sha256" in workflow
    assert "needs.build.outputs.sdist_sha256" in workflow
    assert 'python-version: ["3.12", "3.13"]' in workflow
    assert 'django-version: ["5.2", "6.0", "6.1"]' in workflow
