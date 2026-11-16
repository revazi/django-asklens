"""Replay the public tutorial in an existing isolated core-wheel environment.

Installation and Django matrix selection belong to wheel-smoke.sh. This runner
copies the real consumer and reads commands/expected rows from the public guide;
it never generates a substitute application or authenticates a public release.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import runpy
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

# Executing through -c preserves the copied consumer's normal import path,
# rather than adding any repository directory to PYTHONPATH/sys.path.
BOOTSTRAP = (
    "import runpy, sys; "
    "scope = runpy.run_path(sys.argv[1]); "
    "scope['child_main'](sys.argv[2:])"
)
COMMAND_STEPS = ("setup", "alice", "bob", "empty", "denied", "unmatched", "tests")
DATA_STEPS = ("alice-data", "bob-data")


class TutorialFailure(RuntimeError):
    """A guide, package, isolation, or behavior mismatch must fail CI."""


def read_tutorial(guide: Path) -> dict[str, object]:
    """Require exactly one fenced block for each explicitly tagged step."""
    text = guide.read_text(encoding="utf-8")
    pattern = re.compile(
        r"<!-- asklens-smoke:([a-z-]+) -->\n"
        r"```(bash|json)\n(.*?)\n```",
        re.DOTALL,
    )
    blocks: dict[str, object] = {}
    for match in pattern.finditer(text):
        label, language, content = match.groups()
        if label in blocks:
            raise TutorialFailure(f"Duplicate tutorial step: {label}")
        if label in COMMAND_STEPS and language == "bash":
            commands = []
            for line in content.splitlines():
                parts = shlex.split(line)
                if len(parts) < 3 or parts[:2] != [".venv/bin/python", "manage.py"]:
                    raise TutorialFailure(f"Invalid consumer command in {label}")
                commands.append(parts[2:])
            if not commands:
                raise TutorialFailure(f"Empty tutorial step: {label}")
            blocks[label] = commands
        elif label in DATA_STEPS and language == "json":
            try:
                rows = json.loads(content)
            except json.JSONDecodeError as exc:
                raise TutorialFailure(f"Invalid expected rows in {label}") from exc
            if not isinstance(rows, list) or not rows:
                raise TutorialFailure(f"Expected nonempty example rows in {label}")
            blocks[label] = rows
        else:
            raise TutorialFailure(f"Unknown tutorial step or language: {label}")
    if set(blocks) != set(COMMAND_STEPS + DATA_STEPS):
        raise TutorialFailure("Missing required marked tutorial steps")
    if [command[0] for command in blocks["setup"]] != [
        "migrate",
        "check",
        "check_asklens",
        "seed_quickstart",
    ]:
        raise TutorialFailure("Missing/reordered tutorial setup commands")
    if [command[0] for command in blocks["tests"]] != ["test", "makemigrations"]:
        raise TutorialFailure("Missing tutorial tests/migration check")
    # Each result is checked separately: do not accept extra commands whose
    # output could mask failure, or quietly ignore a guide edit.
    for label in ("alice", "bob", "empty", "denied", "unmatched"):
        if len(blocks[label]) != 1:
            raise TutorialFailure(f"Expected exactly one command in {label}")
        if blocks[label][0][0] != "ask_orders":
            raise TutorialFailure(f"Expected question orchestration in {label}")
    return blocks


def assert_installed_wheel(wheel: Path, source: Path, mode: str = "core") -> None:
    """Check actual installed bytes, not merely a version/direct_url string."""
    import django_asklens

    package = Path(django_asklens.__file__).resolve().parent
    if not package.is_relative_to(Path(sys.prefix).resolve()):
        raise TutorialFailure("AskLens was not imported from the isolated environment")
    if package.is_relative_to(source):
        raise TutorialFailure("Checkout-shadowed AskLens import")
    with zipfile.ZipFile(wheel) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.startswith("django_asklens/") and not name.endswith("/")
        ]
        if not names:
            raise TutorialFailure("Candidate wheel contains no AskLens package")
        for name in names:
            installed = package / name.removeprefix("django_asklens/")
            if not installed.is_file() or installed.read_bytes() != archive.read(name):
                raise TutorialFailure("Installed package bytes differ from candidate")
    assert_import_isolation(source, mode)


def assert_import_isolation(source: Path, mode: str = "core") -> None:
    """Allow only the selected extra, before and after every consumer step."""
    allowed = {"core": None, "api": "rest_framework", "mcp": "fastmcp"}[mode]
    forbidden = {"tests", "rest_framework", "fastmcp"} - {allowed}
    for optional in ("rest_framework", "fastmcp"):
        present = importlib.util.find_spec(optional) is not None
        if optional != allowed and present:
            raise TutorialFailure(f"Unselected optional dependency present: {optional}")
        if optional == allowed and not present:
            raise TutorialFailure(f"Selected optional dependency missing: {optional}")
    for name, module in tuple(sys.modules.items()):
        if name.split(".")[0] in forbidden:
            raise TutorialFailure(f"Forbidden consumer import: {name}")
        filename = getattr(module, "__file__", None)
        if name.startswith("django_asklens") and filename:
            path = Path(filename).resolve()
            if path.is_relative_to(source) or not path.is_relative_to(
                Path(sys.prefix).resolve()
            ):
                raise TutorialFailure("AskLens module escaped installed environment")


def child_main(arguments: list[str]) -> None:
    """A guard failure must never look like an expected CLI denial (exit 1)."""
    try:
        guarded_step(arguments)
    except TutorialFailure as exc:
        print(f"Tutorial guard failure: {str(exc)[:500]}", file=sys.stderr)
        raise SystemExit(70) from None
    except Exception:
        print("Unexpected tutorial guard failure", file=sys.stderr)
        raise SystemExit(70) from None


def guarded_step(arguments: list[str]) -> None:
    """Child entry: execute a guide command with network and import guards."""
    source, wheel = (Path(value).resolve() for value in arguments[:2])
    label, *command = arguments[2:]
    adapter_mode = (
        label.removeprefix("adapter-") if label.startswith("adapter-") else None
    )
    mode = adapter_mode or "core"
    assert_installed_wheel(wheel, source, mode)
    if Path.cwd().resolve().is_relative_to(source):
        raise TutorialFailure("Consumer execution is inside the source checkout")
    os.environ["DJANGO_SETTINGS_MODULE"] = (
        ADAPTER_RECIPES[mode][2] if adapter_mode else "quickstart.settings"
    )
    with (
        patch(
            "socket.socket.connect", side_effect=TutorialFailure("Network forbidden")
        ),
        patch(
            "socket.create_connection", side_effect=TutorialFailure("Network forbidden")
        ),
        patch(
            "urllib.request.urlopen", side_effect=TutorialFailure("Network forbidden")
        ),
    ):
        import django

        django.setup()
        if label == "audit":
            verify_audit()
            assert_import_isolation(source)
            return

        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from shop.models import Order

        rejected = label in {"denied", "unmatched"}
        capture = CaptureQueriesContext(connection) if rejected else nullcontext()
        exit_code = 0
        try:
            with capture:
                sys.argv = ["manage.py", *command]
                runpy.run_path("manage.py", run_name="__main__")
        except SystemExit as exc:
            exit_code = exc.code
        finally:
            assert_import_isolation(source, mode)
            if rejected:
                table = connection.ops.quote_name(Order._meta.db_table)
                if any(table in query["sql"] for query in capture):
                    raise TutorialFailure("Rejected question queried Order data")
        raise SystemExit(exit_code)


def verify_audit() -> None:
    """Only the five tutorial question attempts may populate this fresh DB."""
    from django.conf import settings

    from django_asklens.models import SemanticQueryRun

    config = settings.DJANGO_ASKLENS
    if config["LLM_BACKEND"] != "dummy" or config["AUDIT_INCLUDE_CONTENT"] is not False:
        raise TutorialFailure("Offline/metadata-only tutorial settings changed")
    records = list(SemanticQueryRun.objects.all())
    if len(records) != 5:
        raise TutorialFailure("Expected one audit record per tutorial question")
    if sorted(record.status for record in records) != ["failed"] * 2 + ["success"] * 3:
        raise TutorialFailure("Unexpected tutorial audit outcomes")
    for record in records:
        if record.question != "" or set(record.plan) - {"resource", "intent"}:
            raise TutorialFailure("Audit retained question/full plan content")


def consumer_environment() -> dict[str, str]:
    """Do not inherit source import paths or a host project's Django policy."""
    return {
        key: value
        for key, value in os.environ.items()
        if key
        not in {"PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE", "DJANGO_SETTINGS_MODULE"}
        and not key.startswith("DJANGO_ASKLENS")
    } | {"PYTHONNOUSERSITE": "1"}


def run_command(
    project: Path,
    source: Path,
    wheel: Path,
    label: str,
    command: list[str],
    *,
    extra_environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-s",
            "-c",
            BOOTSTRAP,
            str(Path(__file__).resolve()),
            str(source),
            str(wheel),
            label,
            *command,
        ],
        cwd=project,
        env=consumer_environment() | (extra_environment or {}),
        text=True,
        capture_output=True,
        timeout=90,
    )


def require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        # Default input is committed synthetic fixture/guide code, not customer
        # data. Bound failure output; never dump the environment or provider I/O.
        detail = (result.stdout + result.stderr)[-4000:]
        raise TutorialFailure(
            f"Tutorial {label} failed ({result.returncode}):\n{detail}"
        )


def verify_response(
    result: subprocess.CompletedProcess[str], label: str, expected: object
) -> None:
    if result.returncode == 70:
        require_success(result, f"{label} guard")
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise TutorialFailure(f"Invalid tutorial response: {label}") from exc
    if label in {"denied", "unmatched"}:
        code = (
            "asklens.member.unavailable"
            if label == "denied"
            else "asklens.provider.failed"
        )
        if result.returncode != 1 or document.get("response_type") != "error":
            raise TutorialFailure(f"Expected nonzero safe rejection: {label}")
        if document.get("error", {}).get("code") != code:
            raise TutorialFailure(f"Unexpected safe error code: {label}")
    else:
        require_success(result, label)
        query_result = document.get("result", {})
        if document.get("response_type") != "query":
            raise TutorialFailure(f"Expected query response: {label}")
        if query_result.get("data") != expected:
            raise TutorialFailure(f"Tutorial expected rows differ: {label}")
        if query_result.get("result_metadata", {}).get("truncated") is not False:
            raise TutorialFailure(f"Missing/unexpected truncation metadata: {label}")
        if query_result.get("row_count") != len(expected):
            raise TutorialFailure(f"Incorrect tutorial row count: {label}")


def replay(source: Path, wheel: Path, guide: Path) -> None:
    """Reuse an already-installed wheel; own and clean only the copied project."""
    blocks = read_tutorial(guide)
    assert_installed_wheel(wheel, source)
    parent = Path.cwd().resolve()
    if parent.is_relative_to(source):
        raise TutorialFailure("Run the tutorial smoke outside the source checkout")
    print(f"candidate_wheel_sha256={hashlib.sha256(wheel.read_bytes()).hexdigest()}")
    print(f"candidate_version={importlib.metadata.version('django-asklens')}")
    print(f"installed_package={importlib.util.find_spec('django_asklens').origin}")
    with tempfile.TemporaryDirectory(prefix="asklens-tutorial-", dir=parent) as owned:
        project = Path(owned)
        try:
            shutil.copytree(
                source / "examples" / "quickstart",
                project,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "db.sqlite3", ".venv", "artifacts"
                ),
            )
            for command in blocks["setup"]:
                require_success(
                    run_command(project, source, wheel, "setup", command), "setup"
                )
            for label in ("alice", "bob", "empty", "denied", "unmatched"):
                expected = blocks.get(f"{label}-data", [])
                result = run_command(project, source, wheel, label, blocks[label][0])
                verify_response(result, label, expected)
                print(f"tutorial_step={label}:passed")
            require_success(run_command(project, source, wheel, "audit", []), "audit")
            for command in blocks["tests"]:
                require_success(
                    run_command(project, source, wheel, "tests", command), "tests"
                )
        finally:
            print("tutorial_cleanup=owned-directory-only")
    print("tutorial_cleanup=complete")
    print(
        "PASS public tutorial exact-candidate-wheel replay (not public artifact proof)"
    )


# One source of truth for each guide's executable adapter entry point. The
# installer/environment lifecycle and guarded child runner are shared with core.
ADAPTER_RECIPES = {
    "core": ("usage.md", "shop.admin_recipe", "quickstart.web_settings"),
    "api": ("usage.md", "shop.api_recipe", "quickstart.api_settings"),
    "mcp": ("mcp-integration.md", "shop.mcp_recipe", "quickstart.mcp_settings"),
}


def read_adapter_command(guide: Path, mode: str) -> list[str]:
    matches = re.findall(
        rf"<!-- asklens-adapter:{mode} -->\n```bash\n(.*?)\n```",
        guide.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    if len(matches) != 1:
        raise TutorialFailure("Missing/duplicate adapter recipe command")
    _, module, settings_module = ADAPTER_RECIPES[mode]
    command = shlex.split(matches[0])
    expected = [
        ".venv/bin/python",
        "manage.py",
        "test",
        module,
        f"--settings={settings_module}",
    ]
    if command != expected:
        raise TutorialFailure("Unexpected adapter recipe command")
    return command[2:]


def replay_adapter(source: Path, wheel: Path, mode: str) -> None:
    guide = source / "docs" / ADAPTER_RECIPES[mode][0]
    command = read_adapter_command(guide, mode)
    assert_installed_wheel(wheel, source, mode)
    parent = Path.cwd().resolve()
    if parent.is_relative_to(source):
        raise TutorialFailure("Run the adapter smoke outside the source checkout")
    print(f"candidate_wheel_sha256={hashlib.sha256(wheel.read_bytes()).hexdigest()}")
    print(f"adapter_recipe={mode}")
    with tempfile.TemporaryDirectory(prefix="asklens-adapter-", dir=parent) as owned:
        try:
            shutil.copytree(
                source / "examples" / "quickstart",
                owned,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "db.sqlite3", ".venv", "artifacts"
                ),
            )
            outcome = run_command(
                Path(owned), source, wheel, f"adapter-{mode}", command
            )
            require_success(outcome, f"adapter-{mode}")
            if "Ran 3 tests" not in outcome.stderr:
                raise TutorialFailure("Adapter recipe did not execute its test cases")
            browser_python = os.environ.get("ASKLENS_BROWSER_PYTHON")
            if mode == "api" and browser_python:
                interpreter = Path(browser_python)
                if not interpreter.is_absolute() or not interpreter.is_file():
                    raise TutorialFailure(
                        "Browser driver interpreter must be an absolute file"
                    )
                browser = run_command(
                    Path(owned),
                    source,
                    wheel,
                    "adapter-api",
                    [
                        "test",
                        "shop.browser_recipe",
                        "--settings=quickstart.api_settings",
                    ],
                    extra_environment={
                        "ASKLENS_BROWSER_PYTHON": str(interpreter),
                        "ASKLENS_BROWSER_SCRIPT": str(
                            source / "tests/e2e/quickstart_table.py"
                        ),
                    },
                )
                require_success(browser, "installed API browser")
                if "Ran 1 test" not in browser.stderr:
                    raise TutorialFailure("Installed browser recipe did not execute")
                print("PASS installed candidate API browser (local synthetic HTTP)")
        finally:
            print("adapter_cleanup=owned-directory-only")
    print("adapter_cleanup=complete")
    print(f"PASS installed candidate {mode} recipe (not public artifact/wire proof)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument(
        "--guide", type=Path, help="Alternate guide for mismatch testing only"
    )
    parser.add_argument("--adapter", choices=ADAPTER_RECIPES)
    args = parser.parse_args()
    source = args.source_root.resolve()
    if args.adapter:
        if args.guide:
            parser.error("--guide is only available for the core tutorial replay")
        replay_adapter(source, args.wheel.resolve(), args.adapter)
    else:
        guide = args.guide or source / "docs" / "quickstart-app.md"
        replay(source, args.wheel.resolve(), guide)


if __name__ == "__main__":
    main()
