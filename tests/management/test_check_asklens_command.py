"""Acceptance tests for the privacy-safe AskLens registry diagnostic."""

from __future__ import annotations

from io import StringIO
from typing import Any
from unittest.mock import Mock

import pytest
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from tests.test_project.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_default_registry():
    """Keep command registry evidence independent from other tests."""

    default_registry.clear()
    yield
    default_registry.clear()


def call_check(*args: str) -> tuple[str, str]:
    """Run the command without terminal color and capture both streams."""

    stdout = StringIO()
    stderr = StringIO()
    call_command(
        "check_asklens",
        *args,
        stdout=stdout,
        stderr=stderr,
        no_color=True,
    )
    return stdout.getvalue(), stderr.getvalue()


def expected_summary(
    *,
    resources: int,
    global_resources: int,
    context_scoped_resources: int,
    fields: int,
    metrics: int,
    status: str,
) -> str:
    """Return the exact provisional command output."""

    return (
        "AskLens registry summary\n"
        f"Resources: {resources}\n"
        f"Global resources: {global_resources}\n"
        f"Context-scoped resources: {context_scoped_resources}\n"
        f"Fields: {fields}\n"
        f"Metrics: {metrics}\n"
        f"Status: {status}\n"
    )


def test_command_is_discovered_with_only_the_fail_on_empty_custom_flag() -> None:
    """The core Django app discovers the intentionally narrow command contract."""

    assert get_commands()["check_asklens"] == "django_asklens"

    from django_asklens.management.commands.check_asklens import Command

    parser = Command().create_parser("manage.py", "check_asklens")
    action = next(item for item in parser._actions if item.dest == "fail_on_empty")
    assert action.option_strings == ["--fail-on-empty"]
    assert action.default is False
    assert "Exit nonzero" in action.help


def test_empty_registry_is_reported_without_failing_by_default(
    django_assert_num_queries,
) -> None:
    """An empty registry is visible but remains optional by default."""

    with django_assert_num_queries(0):
        stdout, stderr = call_check()

    assert stdout == expected_summary(
        resources=0,
        global_resources=0,
        context_scoped_resources=0,
        fields=0,
        metrics=0,
        status="EMPTY",
    )
    assert stderr == ""


def test_fail_on_empty_reports_summary_then_exits_nonzero(
    django_assert_num_queries,
) -> None:
    """Deploy checks can opt into deterministic empty-registry failure."""

    stdout = StringIO()
    stderr = StringIO()
    with (
        django_assert_num_queries(0),
        pytest.raises(CommandError, match="^AskLens registry is empty\\.$"),
    ):
        call_command(
            "check_asklens",
            "--fail-on-empty",
            stdout=stdout,
            stderr=stderr,
            no_color=True,
        )

    assert stdout.getvalue() == expected_summary(
        resources=0,
        global_resources=0,
        context_scoped_resources=0,
        fields=0,
        metrics=0,
        status="EMPTY",
    )
    assert stderr.getvalue() == ""


def test_summary_counts_only_safe_metadata_without_invoking_scope_provider(
    django_assert_num_queries,
) -> None:
    """The command emits counts only and never resolves request-aware scope."""

    private_markers = {
        "private_tenant_resource_88",
        "private_field_88",
        "internal_notes",
        "private_metric_88",
        "private.permission.88",
        "private-tenant-identifier-88",
    }
    provider_calls: list[Any] = []

    def forbidden_scope_provider(request: Any):
        provider_calls.append(request)
        raise AssertionError("The diagnostic invoked a scope provider")

    common = {
        "model": Order,
        "timezone": "UTC",
        "fields": {
            "private_field_88": {
                "binding": "internal_notes",
                "type": "string",
                "nullable": False,
                "requires_permission": "private.permission.88",
            }
        },
        "metrics": [
            Metric(
                "private_metric_88",
                op="count",
                binding="internal_notes",
                result_type="integer",
                requires_permission="private.permission.88",
            )
        ],
        "requires_permission": "private.permission.88",
    }
    default_registry.register(
        **common,
        name="private_tenant_resource_88",
        scope_mode="global",
    )
    default_registry.register(
        **common,
        name="private-tenant-identifier-88",
        scope_mode="context_scoped",
        scope_provider=forbidden_scope_provider,
    )

    with django_assert_num_queries(0):
        stdout, stderr = call_check("--fail-on-empty")

    assert stdout == expected_summary(
        resources=2,
        global_resources=1,
        context_scoped_resources=1,
        fields=2,
        metrics=2,
        status="OK",
    )
    assert stderr == ""
    assert provider_calls == []
    for marker in private_markers:
        assert marker not in stdout


def test_counts_are_not_configuration_or_provider_readiness(
    settings, monkeypatch, django_assert_num_queries
) -> None:
    """Invalid runtime settings do not broaden the metadata-only command."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "private-invalid-mode-187",
        "LLM_BACKEND": "openai_compatible",
        "LLM_API_KEY": "synthetic-not-a-credential-187",
        "DUMMY_PLANS": "private-invalid-plans-187",
    }
    default_registry.register(
        timezone="UTC",
        model=Order,
        name="private-resource-187",
        scope_mode="global",
        fields={
            "private-field-187": {
                "binding": "internal_notes",
                "type": "string",
                "nullable": False,
            }
        },
    )
    traps = []
    for path in (
        "django_asklens.llms.factory.get_llm_provider",
        "django_asklens.llms.dummy.DummyProvider.complete_json",
        "django_asklens.llms.openai_compatible.OpenAICompatibleProvider.complete_json",
        "django_asklens.permissions.get_request_permissions",
    ):
        trap = Mock(side_effect=AssertionError("The command resolved runtime policy"))
        monkeypatch.setattr(path, trap)
        traps.append(trap)

    with django_assert_num_queries(0):
        stdout, stderr = call_check("--fail-on-empty")

    assert stdout == expected_summary(
        resources=1,
        global_resources=1,
        context_scoped_resources=0,
        fields=1,
        metrics=0,
        status="OK",
    )
    assert stderr == ""
    for trap in traps:
        trap.assert_not_called()
