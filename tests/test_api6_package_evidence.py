"""Acceptance evidence for API-6 optional-package and route parity checks."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE_SNAPSHOT = ROOT / ".github" / "scripts" / "api_route_snapshot.py"
WHEEL_SMOKE_SHELL = ROOT / ".github" / "scripts" / "wheel-smoke.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_source_to_wheel_route_parity_harness_is_wired_into_ci() -> None:
    """The API wheel smoke must compare one shared source/wheel route probe."""

    assert ROUTE_SNAPSHOT.is_file(), "API-6 route snapshot helper is missing"

    snapshot_helper = ROUTE_SNAPSHOT.read_text(encoding="utf-8")
    wheel_smoke = WHEEL_SMOKE_SHELL.read_text(encoding="utf-8")
    ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    for route in (
        "/asklens/catalog/",
        "/asklens/capabilities/",
        "/asklens/query/",
        "/asklens/runs/<int:pk>/",
    ):
        assert route in snapshot_helper
    assert "query_success" in snapshot_helper
    assert "query_capabilities_help" in snapshot_helper
    assert 'choices=("source", "wheel")' in snapshot_helper
    assert "--compare" in snapshot_helper

    assert "ASKLENS_SOURCE_API_SNAPSHOT" in wheel_smoke
    assert "api_route_snapshot.py" in wheel_smoke
    assert "--provenance wheel" in wheel_smoke
    assert "--compare" in wheel_smoke

    assert "Snapshot source API route behavior" in ci_workflow
    assert "--provenance source" in ci_workflow
    assert "ASKLENS_SOURCE_API_SNAPSHOT" in ci_workflow
