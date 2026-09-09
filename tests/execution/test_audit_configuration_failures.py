"""Audit configuration errors stay typed and cannot replace safe rejections."""

import json
import traceback
from unittest.mock import Mock

import pytest

from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import execute_plan
from django_asklens.execution.audit import _resolve_audit_policy_and_sink
from django_asklens.querying import execute_asklens_query_request
from tests.execution.test_facade import build_registry, request_with, status_plan

pytestmark = pytest.mark.django_db

PRIVATE_DIAGNOSTIC = "private-audit-diagnostic-82"
MISSING_SINK = "private_audit_backend_82.missing_sink"
BINDING_ERROR = {
    "code": "asklens.binding.invalid",
    "message": "The query plan could not be bound safely.",
}
PARSE_ERROR = {
    "code": "asklens.parse.invalid",
    "message": "The query plan could not be parsed.",
    "pointer": "/presentation",
}
INVALID_CONFIGURATIONS = [
    pytest.param({"AUDIT_MODE": PRIVATE_DIAGNOSTIC}, id="unknown-mode"),
    pytest.param({"AUDIT_MODE": [PRIVATE_DIAGNOSTIC]}, id="list-mode"),
    pytest.param({"AUDIT_MODE": {PRIVATE_DIAGNOSTIC: True}}, id="dict-mode"),
    pytest.param(
        {"AUDIT_INCLUDE_CONTENT": PRIVATE_DIAGNOSTIC}, id="non-boolean-content"
    ),
    pytest.param({"AUDIT_MODE": "custom", "AUDIT_SINK": 42}, id="not-callable-sink"),
    pytest.param(
        {"AUDIT_MODE": "custom", "AUDIT_SINK": MISSING_SINK}, id="missing-import"
    ),
]


@pytest.fixture(autouse=True)
def no_execution_or_fallback(monkeypatch, django_assert_num_queries):
    """Configuration failure cannot execute, call providers, or use another sink."""

    traps = []
    for path in (
        "django_asklens.execution.runner._prepare_query_plan",
        "django_asklens.execution.audit._write_database_audit",
        "django_asklens.querying.plan_question",
        "django_asklens.querying.plan_asklens_response",
    ):
        trap = Mock(side_effect=AssertionError("Unexpected execution or fallback."))
        monkeypatch.setattr(path, trap)
        traps.append(trap)
    with django_assert_num_queries(0):
        yield
    for trap in traps:
        trap.assert_not_called()


@pytest.mark.parametrize("configuration", INVALID_CONFIGURATIONS)
def test_facade_rejects_invalid_audit_configuration_safely(
    configuration, settings
) -> None:
    """The public facade must expose only a safe binding error, before any SQL."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled", **configuration}
    with pytest.raises(PublicAskLensError) as caught:
        execute_plan(
            status_plan(),
            request=request_with("shop.view_orders"),
            registry=build_registry(),
        )

    assert public_error_payload(caught.value) == BINDING_ERROR
    assert str(caught.value) == BINDING_ERROR["message"]
    formatted = "".join(traceback.format_exception(caught.value))
    for private in (PRIVATE_DIAGNOSTIC, "private_audit_backend_82"):
        assert private not in formatted


@pytest.mark.parametrize("configuration", INVALID_CONFIGURATIONS)
def test_invalid_audit_configuration_preserves_original_parse_rejection(
    configuration, settings
) -> None:
    """External rejection auditing cannot replace a safe parse error or pointer."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled", **configuration}
    outcome = execute_asklens_query_request(
        request_with(),
        question="Show orders",
        provided_plan={},
        provided_presentation={"kind": PRIVATE_DIAGNOSTIC},
    )

    assert outcome.status_code == 400
    assert outcome.run is None
    assert outcome.payload == {
        "question": "Show orders",
        "status": "failed",
        "error": PARSE_ERROR,
    }
    assert PRIVATE_DIAGNOSTIC not in json.dumps(outcome.payload)


@pytest.mark.parametrize("exception_type", [ImportError, RuntimeError])
def test_sink_module_initialization_errors_are_normalized(
    exception_type, settings, monkeypatch
) -> None:
    """Import-time host/dependency errors follow the same safe binding boundary."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "custom", "AUDIT_SINK": MISSING_SINK}
    importer = Mock(side_effect=exception_type(PRIVATE_DIAGNOSTIC))
    monkeypatch.setattr("django_asklens.execution.audit.import_string", importer)
    with pytest.raises(PublicAskLensError) as caught:
        execute_plan(status_plan(), request=request_with(), registry=build_registry())

    importer.assert_called_once_with(MISSING_SINK)
    assert public_error_payload(caught.value) == BINDING_ERROR
    assert PRIVATE_DIAGNOSTIC not in "".join(traceback.format_exception(caught.value))


def discard_event(_event) -> None:
    """Harmless real dotted-path sink for a successful import control."""


def test_valid_dotted_sink_still_resolves_without_execution(settings) -> None:
    """Normalizing failed imports must not disable a valid custom sink."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "custom",
        "AUDIT_SINK": f"{__name__}.discard_event",
        "AUDIT_INCLUDE_CONTENT": False,
    }
    policy, sink = _resolve_audit_policy_and_sink(request=request_with())
    assert policy.mode == "custom"
    assert policy.include_content is False
    assert sink is discard_event
