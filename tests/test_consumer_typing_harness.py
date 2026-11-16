"""Fail-closed matching for the installed-wheel static consumer runner."""

import runpy
from pathlib import Path

import pytest

check_negative = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/check-consumer-types.py")
)["check_negative"]

SOURCE = "register(name=42)  # E: arg-type\n"
DIAGNOSTIC = "negative.py:1:1: error: Synthetic incorrect argument  [arg-type]\n"


def test_exact_negative_diagnostics():
    assert check_negative(SOURCE, DIAGNOSTIC, 1) == 1
    assert (
        check_negative(
            SOURCE, DIAGNOSTIC + "negative.py:1:1: note: Synthetic definition\n", 1
        )
        == 1
    )


@pytest.mark.parametrize(
    ("source", "output", "returncode"),
    [
        (SOURCE, "", 0),
        (SOURCE, DIAGNOSTIC, 0),
        (SOURCE, DIAGNOSTIC, 2),
        (SOURCE, "", 1),
        (SOURCE, DIAGNOSTIC.replace("arg-type", "assignment"), 1),
        (SOURCE, DIAGNOSTIC.replace(":1:1:", ":2:1:"), 1),
        (SOURCE, DIAGNOSTIC * 2, 1),
        (SOURCE, DIAGNOSTIC + "unexpected output\n", 1),
        ("", "", 1),
    ],
)
def test_negative_diagnostic_mismatch_is_not_success(source, output, returncode):
    with pytest.raises(ValueError):
        check_negative(source, output, returncode)
