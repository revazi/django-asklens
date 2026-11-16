"""Protocol/source drift checks, not participant or public-wheel evidence."""

import json
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_study_selects_public_artifact_and_exact_configured_dummy_question() -> None:
    protocol = (ROOT / "docs/first-run-study.md").read_text(encoding="utf-8")
    identity_block = re.search(
        r"<!-- asklens-study:identity -->\s*```json\s*(.*?)\s*```",
        protocol,
        flags=re.DOTALL,
    )
    assert identity_block is not None
    identity = json.loads(identity_block.group(1))
    installation = (ROOT / "docs/installation.md").read_text(encoding="utf-8")
    assert identity["package_version"] == "0.3.2"
    assert identity["wheel"] == "django_asklens-0.3.2-py3-none-any.whl"
    for key in ("wheel_sha256", "sdist_sha256"):
        assert re.fullmatch(r"[0-9a-f]{64}", identity[key])
        assert identity[key] in installation
    assert identity["example_source_commit"] == (
        "1188e981b5fb4fba468f7ecfcf97e0886aa22874"
    )
    settings = runpy.run_path(str(ROOT / "examples/quickstart/quickstart/settings.py"))
    configuration = settings["DJANGO_ASKLENS"]
    assert configuration["LLM_BACKEND"] == "dummy"
    assert configuration["DUMMY_DEFAULT_PLAN"] is None
    assert configuration["AUDIT_INCLUDE_CONTENT"] is False
    assert identity["question"] == "Show my paid orders"
    assert identity["failure_selector"] == "no-report"
    assert configuration["DUMMY_PLANS"][identity["question"]] == {
        "query_plan": {
            "resource": "orders",
            "intent": "list",
            "select": ["product", "total_cents"],
            "filters": [{"field": "status", "op": "eq", "value": "paid"}],
            "limit": 10,
        }
    }
    for selector in ("alice", "bob", identity["failure_selector"]):
        command = f"manage.py ask_orders '{identity['question']}' --as-user {selector}"
        assert command in protocol


def test_study_and_contract_review_are_discoverable() -> None:
    for path in ("mkdocs.yml", "docs/index.md"):
        contents = (ROOT / path).read_text(encoding="utf-8")
        assert "first-run-study.md" in contents
        assert "integration-contract-review.md" in contents
    assert "integration-contract-review.md" in (
        ROOT / "docs/compatibility.md"
    ).read_text(encoding="utf-8")
