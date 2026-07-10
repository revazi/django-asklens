"""Tests for the opt-in live demo validation command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from django_asklens.catalog.registry import default_registry

pytestmark = pytest.mark.django_db


def configure_complex_dummy_settings(settings) -> None:
    """Configure AskLens like the demo, but with dummy mode for tests."""

    settings.DJANGO_ASKLENS = {
        "LLM_BACKEND": "dummy",
        "API_PERMISSION_CLASSES": [
            "tests.test_project.permissions.CanUseComplexAnalytics",
        ],
        "REQUEST_PERMISSIONS_GETTER": (
            "tests.test_project.permissions.get_request_permissions"
        ),
        "DUMMY_PLANS": {},
        "MAX_ROWS": 100,
        "MAX_JOINS": 2,
        "MAX_METRICS": 5,
        "MAX_GROUP_BY": 3,
    }


@pytest.fixture(autouse=True)
def clear_default_registry() -> None:
    """Keep command tests isolated from global catalog state."""

    default_registry.clear()
    yield
    default_registry.clear()


def test_validate_live_demo_command_requires_live_backend_by_default(settings) -> None:
    """The validation command should not silently run dummy mode as live."""

    configure_complex_dummy_settings(settings)

    with pytest.raises(CommandError, match="live LLM mode"):
        call_command("validate_live_asklens_demo")


def test_validate_live_demo_command_can_run_offline_smoke(settings) -> None:
    """Tests can smoke the command with dummy mode and an explicit flag."""

    configure_complex_dummy_settings(settings)
    call_command("seed_complex_test_project", verbosity=0)
    stdout = StringIO()

    call_command(
        "validate_live_asklens_demo",
        users=["admin"],
        questions=["What can I query?"],
        allow_dummy=True,
        stdout=stdout,
    )

    output = stdout.getvalue()
    assert "AskLens demo validation" in output
    assert "backend: dummy" in output
    assert "api key present: False" in output
    assert "USER admin" in output
    assert "HTTP 200 capabilities" in output
    assert "suggestions=" in output


def test_validate_live_demo_command_reports_missing_seed_user(settings) -> None:
    """A missing seeded user should produce an actionable error."""

    configure_complex_dummy_settings(settings)

    with pytest.raises(CommandError, match="seed_complex_test_project"):
        call_command(
            "validate_live_asklens_demo",
            users=["admin"],
            questions=["What can I query?"],
            allow_dummy=True,
        )
