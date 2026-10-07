from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_HELPER = ROOT / "scripts/download_pypi_artifacts.py"
HANDOFF_VERIFIER = ROOT / "scripts/verify_artifact_handoff.py"
PUBLISH_WORKFLOW = ROOT / ".github/workflows/publish.yml"
RELEASE_RUNBOOK = ROOT / "docs/releasing.md"
MAINTENANCE_ROADMAP = ROOT / "docs/maintenance-roadmap.md"


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_download_helper():
    return load_script("download_pypi_artifacts", DOWNLOAD_HELPER)


def load_handoff_verifier():
    return load_script("verify_artifact_handoff", HANDOFF_VERIFIER)


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


def handoff_artifacts(tmp_path: Path):
    version = "0.3.1"
    artifact_dir = tmp_path / "dist"
    artifact_dir.mkdir()
    wheel = artifact_dir / f"django_asklens-{version}-py3-none-any.whl"
    sdist = artifact_dir / f"django_asklens-{version}.tar.gz"
    wheel.write_bytes(b"reviewed wheel bytes")
    sdist.write_bytes(b"reviewed sdist bytes")
    return (
        artifact_dir,
        version,
        wheel,
        sdist,
        {
            "wheel": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "sdist": hashlib.sha256(sdist.read_bytes()).hexdigest(),
        },
    )


def verify_handoff(verifier, artifacts) -> None:
    artifact_dir, version, _, _, digests = artifacts
    verifier.verify_artifacts(
        artifact_dir,
        version,
        digests["wheel"],
        digests["sdist"],
    )


def changed_digest(digest: str) -> str:
    replacement = "0" if digest[0] != "0" else "1"
    return replacement + digest[1:]


def test_artifact_handoff_accepts_exact_files_and_build_digests(tmp_path):
    verifier = load_handoff_verifier()

    verify_handoff(verifier, handoff_artifacts(tmp_path))


def test_artifact_handoff_rejects_missing_file(tmp_path):
    verifier = load_handoff_verifier()
    artifacts = handoff_artifacts(tmp_path)
    artifacts[3].unlink()

    with pytest.raises(verifier.ArtifactHandoffError):
        verify_handoff(verifier, artifacts)


def test_artifact_handoff_rejects_extra_file(tmp_path):
    verifier = load_handoff_verifier()
    artifacts = handoff_artifacts(tmp_path)
    (artifacts[0] / "unexpected.txt").write_text("unexpected")

    with pytest.raises(verifier.ArtifactHandoffError):
        verify_handoff(verifier, artifacts)


def test_artifact_handoff_rejects_renamed_file(tmp_path):
    verifier = load_handoff_verifier()
    artifacts = handoff_artifacts(tmp_path)
    artifacts[2].rename(artifacts[0] / "renamed.whl")

    with pytest.raises(verifier.ArtifactHandoffError):
        verify_handoff(verifier, artifacts)


def test_artifact_handoff_rejects_duplicate_or_ambiguous_file(tmp_path):
    verifier = load_handoff_verifier()
    artifacts = handoff_artifacts(tmp_path)
    duplicate = artifacts[0] / f"django_asklens-{artifacts[1]}-py2-none-any.whl"
    os.link(artifacts[2], duplicate)

    with pytest.raises(verifier.ArtifactHandoffError):
        verify_handoff(verifier, artifacts)


def test_artifact_handoff_rejects_nested_file(tmp_path):
    verifier = load_handoff_verifier()
    artifacts = handoff_artifacts(tmp_path)
    nested = artifacts[0] / "nested"
    nested.mkdir()
    (nested / artifacts[2].name).write_bytes(artifacts[2].read_bytes())

    with pytest.raises(verifier.ArtifactHandoffError):
        verify_handoff(verifier, artifacts)


def test_artifact_handoff_rejects_symlink(tmp_path):
    verifier = load_handoff_verifier()
    artifacts = handoff_artifacts(tmp_path)
    wheel = artifacts[2]
    target = tmp_path / "outside.whl"
    target.write_bytes(wheel.read_bytes())
    wheel.unlink()
    wheel.symlink_to(target)

    with pytest.raises(verifier.ArtifactHandoffError):
        verify_handoff(verifier, artifacts)


def test_artifact_handoff_rejects_non_regular_file(tmp_path):
    verifier = load_handoff_verifier()
    artifacts = handoff_artifacts(tmp_path)
    sdist = artifacts[3]
    sdist.unlink()
    sdist.mkdir()

    with pytest.raises(verifier.ArtifactHandoffError):
        verify_handoff(verifier, artifacts)


@pytest.mark.parametrize(
    ("version", "wheel_sha256", "sdist_sha256", "message"),
    [
        ("../0.3.1", "0" * 64, "1" * 64, "Invalid version"),
        ("0.3.1", "A" * 64, "1" * 64, "Invalid wheel SHA-256"),
        ("0.3.1", "0" * 64, "short", "Invalid sdist SHA-256"),
    ],
)
def test_artifact_handoff_rejects_malformed_inputs(
    tmp_path, version, wheel_sha256, sdist_sha256, message
):
    verifier = load_handoff_verifier()

    with pytest.raises(verifier.ArtifactHandoffError, match=message):
        verifier.verify_artifacts(tmp_path, version, wheel_sha256, sdist_sha256)


def test_artifact_handoff_rejects_wheel_digest_mismatch(tmp_path):
    verifier = load_handoff_verifier()
    artifacts = handoff_artifacts(tmp_path)
    artifact_dir, version, _, _, digests = artifacts

    with pytest.raises(verifier.ArtifactHandoffError, match="wheel digest"):
        verifier.verify_artifacts(
            artifact_dir,
            version,
            changed_digest(digests["wheel"]),
            digests["sdist"],
        )


def test_artifact_handoff_rejects_sdist_digest_mismatch(tmp_path):
    verifier = load_handoff_verifier()
    artifacts = handoff_artifacts(tmp_path)
    artifact_dir, version, _, _, digests = artifacts

    with pytest.raises(verifier.ArtifactHandoffError, match="sdist digest"):
        verifier.verify_artifacts(
            artifact_dir,
            version,
            digests["wheel"],
            changed_digest(digests["sdist"]),
        )


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
    assert 'wheel, = Path("dist").glob("django_asklens-*.whl")' in workflow
    assert 'sdist, = Path("dist").glob("django_asklens-*.tar.gz")' in workflow


def test_publish_workflow_hands_off_exact_build_artifact():
    workflow = PUBLISH_WORKFLOW.read_text()
    build_job = workflow[workflow.index("  build:") : workflow.index("  publish:")]
    publish_job = workflow[
        workflow.index("  publish:") : workflow.index("  verify-published:")
    ]

    record = build_job.index("- name: Record exact artifact digests")
    preserve = build_job.index(
        "- name: Preserve the exact distributions for the protected job"
    )
    assert record < preserve

    upload_step = build_job[preserve:]
    assert workflow.count("uses: actions/upload-artifact@") == 1
    assert "uses: actions/upload-artifact@" in upload_step
    assert "name: release-distributions" in upload_step
    assert "dist/*.whl" in upload_step
    assert "dist/*.tar.gz" in upload_step
    assert "if-no-files-found: error" in upload_step

    retrieve = publish_job.index("- name: Retrieve the exact reviewed distributions")
    guard = publish_job.index("- name: Authenticate the artifact handoff")
    download_step = publish_job[retrieve:guard]
    assert workflow.count("uses: actions/download-artifact@") == 1
    assert "uses: actions/download-artifact@" in download_step
    assert "name: release-distributions" in download_step
    assert "path: dist" in download_step


def test_publish_workflow_authenticates_build_outputs_before_publication():
    workflow = PUBLISH_WORKFLOW.read_text()
    publish_job = workflow[
        workflow.index("  publish:") : workflow.index("  verify-published:")
    ]

    checkout = publish_job.index(
        "- name: Check out the published release tag without credentials"
    )
    retrieve = publish_job.index("- name: Retrieve the exact reviewed distributions")
    guard = publish_job.index("- name: Authenticate the artifact handoff")
    publish = publish_job.index("- name: Publish distributions to PyPI")
    assert checkout < retrieve < guard < publish

    guard_step = publish_job[guard:publish]
    for build_output in (
        "needs.build.outputs.version",
        "needs.build.outputs.wheel_sha256",
        "needs.build.outputs.sdist_sha256",
    ):
        assert build_output in guard_step
    for argument in (
        '--version "$RELEASE_VERSION"',
        '--wheel-sha256 "$WHEEL_SHA256"',
        '--sdist-sha256 "$SDIST_SHA256"',
    ):
        assert argument in guard_step

    checkout_step = publish_job[checkout:retrieve]
    assert "ref: ${{ github.event.release.tag_name }}" in checkout_step
    assert "persist-credentials: false" in checkout_step
    assert "scripts/verify_artifact_handoff.py" in guard_step


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
        "`0.3.1` is the current published maintenance release",
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
        "`v0.2.0`, `v0.3.0`, and `v0.3.1`",
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
