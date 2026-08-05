"""Narrow static assertions for CI dependency-audit workflow wiring."""

from __future__ import annotations

from pathlib import Path


def _extract_job_block(workflow: str, job_name: str) -> str:
    lines = workflow.splitlines()
    header = f"  {job_name}:"
    start = None
    for index, line in enumerate(lines):
        if line == header:
            start = index
            break

    assert start is not None, f"Job '{job_name}' not found"

    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    "):
            if line != lines[start]:
                break
        block.append(line)

    return "\n".join(block)


def _extract_permissions_block(workflow: str) -> str:
    lines = workflow.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("permissions:"):
            start = index
            break

    assert start is not None, "Workflow permissions block not found"

    block = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.startswith("  "):
            break
        block.append(line)

    return "\n".join(block)


def test_dependency_audit_job_has_locked_audit_command_and_no_bypasses():
    workflow = Path(".github/workflows/ci.yml").read_text()
    block = _extract_job_block(workflow, "dependency-audit")
    lines = block.splitlines()
    trimmed_lines = [line.strip() for line in lines]

    assert "uses: astral-sh/setup-uv@v7" in trimmed_lines
    assert 'version: "0.12.1"' in trimmed_lines

    run_lines = [line.strip() for line in lines if line.strip().startswith("run:")]
    assert run_lines == ["run: uv audit --locked --preview-features audit-command"]

    banned_tokens = [
        "uv sync",
        "uv pip install",
        "uv install",
        "--ignore",
        "--ignore-until-fixed",
        "continue-on-error:",
        "upload-artifact",
        "security-events",
        "sarif",
        "actions/upload-artifact",
        "GITHUB_TOKEN",
        "secrets.",
    ]
    for token in banned_tokens:
        assert token not in block


def test_dependency_audit_job_and_workflow_permissions_are_minimal():
    workflow = Path(".github/workflows/ci.yml").read_text()

    permissions_block = _extract_permissions_block(workflow)
    permissions = [
        line.strip() for line in permissions_block.splitlines()[1:] if line.strip()
    ]
    assert permissions == ["contents: read"]

    audit_block = _extract_job_block(workflow, "dependency-audit")
    assert "permissions:" not in audit_block
    assert "  dependency-audit:" in workflow
