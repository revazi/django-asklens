"""Offline negative/unit checks for the installed tutorial replay boundary."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".github/scripts/quickstart_smoke.py"
GUIDE = ROOT / "docs/quickstart-app.md"


def load_helper():
    spec = importlib.util.spec_from_file_location("quickstart_smoke", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def helper():
    return load_helper()


def test_public_commands_and_expected_rows_are_read_not_regenerated(helper):
    blocks = helper.read_tutorial(GUIDE)
    assert blocks["alice"] == [
        ["ask_orders", "Show my paid orders", "--as-user", "alice"]
    ]
    assert blocks["bob-data"] == [{"product": "South membership", "total_cents": 9900}]
    assert blocks["tests"][-1] == ["makemigrations", "--check", "--dry-run"]


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        ("<!-- asklens-smoke:setup -->", "", "Missing required"),
        ("<!-- asklens-smoke:bob -->", "<!-- asklens-smoke:alice -->", "Duplicate"),
        ("<!-- asklens-smoke:bob -->", "<!-- asklens-smoke:unknown -->", "Unknown"),
        (
            ".venv/bin/python manage.py migrate",
            "bash manage.py migrate",
            "Invalid consumer",
        ),
        (".venv/bin/python manage.py check\n", "", "setup commands"),
        (".venv/bin/python manage.py test shop\n", "", "tests/migration check"),
        ('[{"product": "South membership", "total_cents": 9900}]', "[]", "nonempty"),
    ],
)
def test_missing_or_malformed_public_steps_fail(
    helper, tmp_path, before, after, message
):
    guide = tmp_path / "guide.md"
    guide.write_text(GUIDE.read_text().replace(before, after), encoding="utf-8")
    with pytest.raises(helper.TutorialFailure, match=message):
        helper.read_tutorial(guide)


def response(document, status=0):
    return subprocess.CompletedProcess([], status, json.dumps(document), "")


def test_changed_documented_rows_fail_behavioral_comparison(helper):
    result = response(
        {
            "response_type": "query",
            "result": {
                "data": [{"product": "unexpected"}],
                "row_count": 1,
                "result_metadata": {"truncated": False},
            },
        }
    )
    with pytest.raises(helper.TutorialFailure, match="expected rows differ"):
        helper.verify_response(result, "alice", [{"product": "documented"}])


def test_empty_result_requires_real_success_and_metadata(helper):
    document = {
        "response_type": "query",
        "result": {
            "data": [],
            "row_count": 0,
            "result_metadata": {"truncated": False},
        },
    }
    helper.verify_response(response(document), "empty", [])
    with pytest.raises(helper.TutorialFailure, match="failed"):
        helper.verify_response(response(document, status=1), "empty", [])
    document["result"]["result_metadata"] = {}
    with pytest.raises(helper.TutorialFailure, match="truncation"):
        helper.verify_response(response(document), "empty", [])


def test_denial_requires_nonzero_exit_and_exact_safe_category(helper):
    document = {
        "response_type": "error",
        "error": {"code": "asklens.member.unavailable"},
    }
    helper.verify_response(response(document, status=1), "denied", [])
    with pytest.raises(helper.TutorialFailure, match="nonzero safe rejection"):
        helper.verify_response(response(document), "denied", [])
    with pytest.raises(helper.TutorialFailure, match="denied guard failed"):
        helper.verify_response(response(document, status=70), "denied", [])
    document["error"]["code"] = "asklens.execute.failed"
    with pytest.raises(helper.TutorialFailure, match="safe error code"):
        helper.verify_response(response(document, status=1), "denied", [])


def test_guard_violation_cannot_masquerade_as_expected_denial(helper, monkeypatch):
    def violated_guard(_):
        raise helper.TutorialFailure("Rejected question queried Order data")

    monkeypatch.setattr(helper, "guarded_step", violated_guard)
    with pytest.raises(SystemExit) as outcome:
        helper.child_main([])
    assert outcome.value.code == 70


def test_environment_drops_host_policy_and_checkout_injection(helper, monkeypatch):
    for key in (
        "PYTHONPATH",
        "PYTHONHOME",
        "DJANGO_SETTINGS_MODULE",
        "DJANGO_ASKLENS_LIVE_LLM",
    ):
        monkeypatch.setenv(key, "must-not-be-inherited")
    environment = helper.consumer_environment()
    assert not set(environment) & {
        "PYTHONPATH",
        "PYTHONHOME",
        "DJANGO_SETTINGS_MODULE",
        "DJANGO_ASKLENS_LIVE_LLM",
    }
    assert environment["PYTHONNOUSERSITE"] == "1"


def test_failure_cleans_only_owned_project(helper, tmp_path, monkeypatch):
    source = tmp_path / "source"
    example = source / "examples/quickstart"
    example.mkdir(parents=True)
    (example / "manage.py").write_text("# synthetic example", encoding="utf-8")
    wheel = tmp_path / "candidate.whl"
    wheel.write_bytes(b"candidate-bytes")
    consumer_root = tmp_path / "owned-parent"
    consumer_root.mkdir()
    sentinel = consumer_root / "caller-owned.txt"
    sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.chdir(consumer_root)
    monkeypatch.setattr(helper, "assert_installed_wheel", lambda *_: None)
    monkeypatch.setattr(helper.importlib.metadata, "version", lambda _: "candidate")
    # Run setup failure inside the actual TemporaryDirectory lifecycle.
    monkeypatch.setattr(helper, "run_command", lambda *_: response({}, status=2))
    with pytest.raises(helper.TutorialFailure, match="setup failed"):
        helper.replay(source, wheel, GUIDE)
    assert sorted(path.name for path in consumer_root.iterdir()) == ["caller-owned.txt"]
    assert (example / "manage.py").is_file()


def test_outside_checkout_execution_is_required(helper, tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(helper, "assert_installed_wheel", lambda *_: None)
    with pytest.raises(helper.TutorialFailure, match="outside the source checkout"):
        helper.replay(ROOT, tmp_path / "unused.whl", GUIDE)


def test_core_installer_opt_in_is_wired_to_existing_matrix():
    shell = (ROOT / ".github/scripts/wheel-smoke.sh").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    manifest = (ROOT / "MANIFEST.in").read_text()
    assert 'case "${ASKLENS_TUTORIAL_SMOKE:-0}" in' in shell
    assert 'if [[ "$mode" != "core" ]]' in shell
    assert "quickstart_smoke.py" in shell
    assert "env -u PYTHONPATH -u PYTHONHOME -u DJANGO_SETTINGS_MODULE" in shell
    assert 'ASKLENS_TUTORIAL_SMOKE: "1"' in workflow
    assert "include .github/scripts/quickstart_smoke.py" in manifest
    subprocess.run(["bash", "-n", ROOT / ".github/scripts/wheel-smoke.sh"], check=True)
