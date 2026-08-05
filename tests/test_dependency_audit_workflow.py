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
            break
        block.append(line)

    return "\n".join(block)


def test_dependency_audit_job_uses_locked_audit_command_and_no_installs():
    workflow = Path(".github/workflows/ci.yml").read_text()
    block = _extract_job_block(workflow, "dependency-audit")

    assert "name: Locked dependency vulnerability audit" in block
    assert "run: uv audit --locked --preview-features audit-command" in block
    assert "continue-on-error:" not in block
    assert "uv sync " not in block
    assert "uv pip install" not in block


def test_workflow_permissions_and_job_exists():
    workflow = Path(".github/workflows/ci.yml").read_text()

    assert "permissions:\n  contents: read" in workflow
    assert "  dependency-audit:" in workflow
