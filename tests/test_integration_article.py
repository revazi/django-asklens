"""Article drift/negative checks; installed execution uses the existing runner."""

import ast
import copy
import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.test_quickstart_wheel_smoke import load_helper, response

ROOT = Path(__file__).resolve().parents[1]
ARTICLE = ROOT / "docs/integration-article.md"


@pytest.fixture
def helper():
    return load_helper()


def test_all_four_commands_and_full_expected_responses_are_read(helper):
    blocks = helper.read_article(ARTICLE)
    assert blocks["success"][0] == helper.ARTICLE_COMMANDS["success"]
    assert blocks["empty-response"]["result"]["data"] == []
    assert blocks["denied-response"]["error"] == {
        "code": "asklens.member.unavailable",
        "message": "A requested query member is unavailable.",
    }
    assert blocks["invalid-response"]["error"] == {
        "code": "asklens.plan.invalid",
        "message": "The query plan is invalid.",
    }


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        ("<!-- asklens-article:success -->", "", "Missing required"),
        (
            "<!-- asklens-article:empty -->",
            "<!-- asklens-article:success -->",
            "Duplicate",
        ),
        (
            "<!-- asklens-article:success -->",
            "<!-- asklens-article:unknown -->",
            "Unknown",
        ),
        ("'Show my paid orders' --as-user alice", "'new wording'", "Unexpected"),
        ('"response_type": "query"', '"response_type": query', "Invalid article"),
    ],
)
def test_article_drift_is_not_silently_ignored(
    helper, tmp_path, before, after, message
):
    guide = tmp_path / "article.md"
    guide.write_text(ARTICLE.read_text().replace(before, after))
    with pytest.raises(helper.TutorialFailure, match=message):
        helper.read_article(guide)


@pytest.mark.parametrize("label", ["success", "empty", "denied", "invalid"])
def test_exact_response_comparison_rejects_extra_fields_and_wrong_exit(helper, label):
    expected = helper.read_article(ARTICLE)[f"{label}-response"]
    actual = copy.deepcopy(expected)
    status = 1 if label in {"denied", "invalid"} else 0
    if status == 0:
        actual["result"]["duration_ms"] = 3
    helper.verify_article_response(response(actual, status), label, expected)
    with pytest.raises(helper.TutorialFailure, match="exit status"):
        helper.verify_article_response(response(actual, 1 - status), label, expected)
    with pytest.raises(helper.TutorialFailure, match="guard failed"):
        helper.verify_article_response(response(actual, 70), label, expected)
    actual["unexpected"] = "synthetic-host-detail"
    with pytest.raises(helper.TutorialFailure, match="response differs"):
        helper.verify_article_response(response(actual, status), label, expected)


@pytest.mark.parametrize("duration", [None, True, -1, "1"])
def test_success_requires_an_actual_nonnegative_duration(helper, duration):
    expected = helper.read_article(ARTICLE)["success-response"]
    actual = copy.deepcopy(expected)
    actual["result"]["duration_ms"] = duration
    with pytest.raises(helper.TutorialFailure, match="duration"):
        helper.verify_article_response(response(actual), "success", expected)


def test_invalid_response_json_cannot_count_as_expected_rejection(helper):
    with pytest.raises(helper.TutorialFailure, match="Invalid article response"):
        helper.verify_article_response(
            subprocess.CompletedProcess([], 1, "not-json", ""), "invalid", {}
        )


def test_registration_and_invalid_envelope_match_the_executed_host_files():
    article = ARTICLE.read_text()
    registration = re.search(
        r"<!-- asklens-article-source:registration -->\n```python\n(.*?)\n```",
        article,
        re.DOTALL,
    )[1]
    assert (
        registration + "\n"
        == (ROOT / "examples/quickstart/shop/asklens_registration.py").read_text()
    )
    envelope = json.loads(
        re.search(
            r"<!-- asklens-article-source:invalid-envelope -->\n```json\n(.*?)\n```",
            article,
            re.DOTALL,
        )[1]
    )
    tree = ast.parse(
        (ROOT / "examples/quickstart/quickstart/invalid_plan_settings.py").read_text()
    )
    config = next(node.value for node in tree.body if isinstance(node, ast.Assign))
    plans = next(
        value
        for key, value in zip(config.keys, config.values, strict=True)
        if isinstance(key, ast.Constant) and key.value == "DUMMY_PLANS"
    )
    assert ast.literal_eval(plans) == {"Show my paid orders": envelope}
    from django_asklens.exceptions import PlanValidationError
    from django_asklens.planning import parse_planner_provider_response

    with pytest.raises(PlanValidationError):
        parse_planner_provider_response(envelope)


def test_article_failure_cleans_only_the_owned_consumer(helper, tmp_path, monkeypatch):
    source = tmp_path / "source"
    (source / "examples/quickstart").mkdir(parents=True)
    (source / "docs").mkdir()
    (source / "docs/quickstart-app.md").write_text(
        (ROOT / "docs/quickstart-app.md").read_text()
    )
    wheel = tmp_path / "candidate.whl"
    wheel.write_bytes(b"synthetic-candidate")
    parent = tmp_path / "consumer-parent"
    parent.mkdir()
    sentinel = parent / "keep.txt"
    sentinel.write_text("keep")
    monkeypatch.chdir(parent)
    monkeypatch.setattr(helper, "assert_installed_wheel", lambda *_: None)
    monkeypatch.setattr(helper.importlib.metadata, "version", lambda _: "candidate")
    monkeypatch.setattr(helper, "run_command", lambda *_: response({}, 70))
    with pytest.raises(helper.TutorialFailure, match="setup failed"):
        helper.replay(source, wheel, ARTICLE, article=True)
    assert list(parent.iterdir()) == [sentinel]


def test_article_reuses_candidate_core_installer_and_never_defaults_on():
    shell = (ROOT / ".github/scripts/wheel-smoke.sh").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert 'case "${ASKLENS_ARTICLE_SMOKE:-0}" in' in shell
    assert '--wheel "$wheel" --article' in shell
    assert 'ASKLENS_ARTICLE_SMOKE: "1"' in workflow
    assert "core-only wheel environment" in shell
    for script in ("scripts/published-package-smoke.sh",):
        assert "ASKLENS_ARTICLE_SMOKE=1" not in (ROOT / script).read_text()
