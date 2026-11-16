#!/usr/bin/env python3
"""Check bounded consumers of a candidate wheel, never an editable checkout."""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/installed_consumer/typing"


def check_negative(source: str, output: str, returncode: int) -> int:
    """Require the exact diagnostic multiset, not merely a failing exit code."""
    expected = Counter(
        (line_number, code)
        for line_number, line in enumerate(source.splitlines(), 1)
        for code in re.findall(r"# E: ([a-z-]+)\s*$", line)
    )
    actual: Counter[tuple[int, str]] = Counter()
    for line in output.splitlines():
        if re.fullmatch(r"negative\.py:\d+:\d+: note: .+", line):
            continue
        match = re.fullmatch(r"negative\.py:(\d+):\d+: error: .* \[([a-z-]+)\]", line)
        if match is None:
            raise ValueError(f"Unexpected negative-fixture diagnostic: {line}")
        actual[int(match[1]), match[2]] += 1
    if not expected or returncode != 1 or actual != expected:
        raise ValueError(
            f"Negative diagnostics differ: missing={expected - actual}, "
            f"unexpected={actual - expected}, exit={returncode}"
        )
    return expected.total()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    if wheel.suffix != ".whl":
        parser.error("Expected a built candidate .whl")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTHON", "MYPY", "DJANGO_", "UV_"))
    }
    # Preserve caches, not project/extra/index configuration. No package extras
    # or typing dependencies are installed into the runtime wheel itself.
    with tempfile.TemporaryDirectory(prefix="asklens-consumer-types-") as directory:
        work = Path(directory).resolve()
        if work.is_relative_to(ROOT):
            raise ValueError("Consumer workspace must be outside the checkout")
        for name in ("positive.py", "negative.py", "mypy.ini"):
            shutil.copyfile(FIXTURES / name, work / name)

        def run(*command: str, cwd: Path = work) -> None:
            subprocess.run(command, cwd=cwd, env=env, check=True)

        requirements = work / "requirements.txt"
        run(
            "uv",
            "export",
            "--locked",
            "--no-default-groups",
            "--group",
            "typing",
            "--no-emit-project",
            "--output-file",
            str(requirements),
            "--quiet",
            cwd=ROOT,
        )
        venv = work / "venv"
        run("uv", "venv", "--python", sys.executable, str(venv), "--quiet")
        python = str(venv / "bin/python")
        run("uv", "pip", "sync", "--python", python, str(requirements), "--quiet")
        run(
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--no-deps",
            str(wheel),
            "--quiet",
        )
        run(
            python,
            "-I",
            "-c",
            "import importlib.util, pathlib, sys; import django_asklens; "
            "p = pathlib.Path(django_asklens.__file__).resolve(); "
            "assert p.is_relative_to(pathlib.Path(sys.prefix).resolve()); "
            "assert (p.parent / 'py.typed').is_file(); "
            "assert importlib.util.find_spec('rest_framework') is None; "
            "assert importlib.util.find_spec('fastmcp') is None; "
            "print('Installed py.typed verified; no optional adapters')",
        )
        mypy = (
            python,
            "-I",
            "-m",
            "mypy",
            "--config-file",
            str(work / "mypy.ini"),
            "--no-error-summary",
            "--no-pretty",
            "--no-color-output",
        )
        run(*mypy, "positive.py")
        negative = subprocess.run(
            (*mypy, "negative.py"),
            cwd=work,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        count = check_negative(
            (work / "negative.py").read_text(), negative.stdout, negative.returncode
        )
        print(f"Installed-wheel typing passed: positive and {count} exact negatives")


if __name__ == "__main__":
    main()
