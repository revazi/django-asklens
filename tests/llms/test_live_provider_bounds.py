"""Offline tests of the opt-in live-test guard; no real credentials or HTTP."""

import io
import json
from types import SimpleNamespace

import pytest

from django_asklens.exceptions import LLMProviderError
from django_asklens.llms.openai_compatible import build_chat_completions_request
from django_asklens.provider_preflight import BASE_URL, MODEL
from tests.evaluation import live_support as live

CANARY = "synthetic-private-value"
CONSENT = {
    "DJANGO_ASKLENS_LIVE_LLM": "1",
    "DJANGO_ASKLENS_LIVE_LLM_CONSENT": live.CONSENT,
}


@pytest.fixture
def inert(monkeypatch):
    calls = []
    monkeypatch.setattr(live, "os", SimpleNamespace(environ=CONSENT))

    def open_request(request, *, timeout):
        calls.append(request)
        assert timeout == 30
        assert json.loads(request.data)["max_completion_tokens"] == 2048
        return io.BytesIO(b"{}")

    monkeypatch.setattr(
        live, "build_opener", lambda *a: SimpleNamespace(open=open_request)
    )
    return calls


def request():
    return build_chat_completions_request(
        base_url=BASE_URL,
        api_key=CANARY,
        model=MODEL,
        messages=(),
        schema={},
        temperature=0,
    )


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"DJANGO_ASKLENS_LIVE_LLM": "1"},
        {"DJANGO_ASKLENS_LIVE_LLM_CONSENT": live.CONSENT},
        {**CONSENT, "PYTEST_XDIST_WORKER": "gw0"},
    ],
)
def test_live_guard_requires_both_flags_and_serial_mode(environ, monkeypatch, inert):
    assert not live.live_enabled(environ)
    monkeypatch.setattr(live, "os", SimpleNamespace(environ=environ))
    with (
        pytest.raises(LLMProviderError),
        live.LiveRequestBudget().transport()(request(), timeout=30),
    ):
        pytest.fail("Consent-bypassing transport")
    assert inert == []


def test_one_request_per_test_and_seven_per_serial_session(inert):
    budget = live.LiveRequestBudget()
    first = budget.transport()
    with first(request(), timeout=30):
        pass
    with pytest.raises(LLMProviderError), first(request(), timeout=30):
        pytest.fail("Repeated request")
    for _ in range(6):
        with budget.transport()(request(), timeout=30):
            pass
    with pytest.raises(LLMProviderError), budget.transport()(request(), timeout=30):
        pytest.fail("Session request cap bypassed")
    assert budget.count == len(inert) == 7


def test_concurrent_live_calls_are_rejected(inert):
    budget = live.LiveRequestBudget()
    with budget.transport()(request(), timeout=30):
        with pytest.raises(LLMProviderError), budget.transport()(request(), timeout=30):
            pytest.fail("Concurrent call")
    assert len(inert) == 1


def test_raw_live_transport_errors_are_not_rendered(inert, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError(CANARY)

    monkeypatch.setattr(live, "build_opener", fail)
    with (
        pytest.raises(LLMProviderError) as exc,
        live.LiveRequestBudget().transport()(request(), timeout=30),
    ):
        pytest.fail("Hostile transport succeeded")
    assert CANARY not in str(exc.value)
    assert exc.value.__suppress_context__


def test_live_transport_rejects_unapproved_configuration(inert):
    with (
        pytest.raises(LLMProviderError),
        live.LiveRequestBudget().transport()(request(), timeout=31),
    ):
        pytest.fail("Unbounded timeout")
    assert inert == []
