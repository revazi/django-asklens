from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_HELPER = ROOT / "scripts/download_pypi_artifacts.py"
PUBLISH_WORKFLOW = ROOT / ".github/workflows/publish.yml"
RELEASE_RUNBOOK = ROOT / "docs/releasing.md"
MAINTENANCE_ROADMAP = ROOT / "docs/maintenance-roadmap.md"


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
    publish_action = (
        "pypa/gh-action-pypi-publish@"
        "dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1"
    )
    assert publish_action in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" not in workflow
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


def test_trusted_publisher_recovery_is_failed_job_only_and_fail_closed():
    runbook = RELEASE_RUNBOOK.read_text()
    normalized = " ".join(runbook.split())

    for required in (
        "## Trusted Publisher incident and recovery",
        "valid OIDC token plus `invalid-publisher`",
        "publisher-configuration or service incident",
        "production PyPI (`pypi.org`) is distinct from TestPyPI",
        "existing-project publisher",
        "distinct from a pending publisher",
        "owner `revazi`",
        "repository `django-asklens`",
        "workflow filename `publish.yml`",
        "environment `pypi`",
        "independently confirm that no release file was uploaded",
        "exactly the same one wheel and one source distribution",
        "use GitHub's **re-run failed jobs** action on that same workflow run",
        "operator-only environment approval",
        "preserve the immutable tag, GitHub Release, artifact filenames",
        "workflow-recorded digests",
        "Preserve the failed attempts as part of the incident record",
    ):
        assert required in normalized

    for prohibition in (
        "move or recreate the tag",
        "upload manually",
        "PyPI token or password fallback",
        "`skip-existing`",
        "overwrite or replace a file",
        "conceal a failed attempt",
    ):
        assert prohibition in normalized

    assert (
        "printing, copying, decoding, or otherwise inspecting the token" in normalized
    )
    assert "repository automation must not change it" in normalized


def test_maintenance_roadmap_separates_patch_and_future_minor_scope():
    roadmap = MAINTENANCE_ROADMAP.read_text()
    normalized = " ".join(roadmap.split())

    for required in (
        "`0.3.1` is the current maintenance milestone",
        "compatible, migration-free",
        "No future version or delivery date is promised",
        "registration and resource APIs",
        "trusted `execute_plan()` / `QueryResult`",
        "namespaced public errors",
        "privacy-safe host observability",
        "HTTP/DRF, MCP, admin, frontend, provider orchestration and internals",
        "`catalog`, `query-plan`, `capabilities`, `result`, and `error`",
        "draft, internal, unversioned, and without negotiation",
        "Async execution, streaming",
        "routing, health checking, or failover",
        "Saved queries",
        "Scheduled audit retention",
        "External telemetry transports",
        "dependency-major policy changes",
        "`v0.2.0` and `v0.3.0`",
        "`0.1.0a1` package remains an unsupported testing artifact",
    ):
        assert required in normalized

    for audit_record in (
        "2026-10-04T09:31:52Z",
        "uv audit --locked --preview-features audit-command",
        "resolved 109 locked packages",
        "no known vulnerabilities",
        "no adverse project statuses in the 108 audited packages",
        "the lock remains unchanged",
        "future lookup failure must be reported as failed evidence",
        "Second-operating-system package-smoke decision",
        "is **deferred**",
    ):
        assert audit_record in normalized

    assert "## `0.2.1` candidates" not in roadmap
    assert "## `0.3.0` release work" not in roadmap
