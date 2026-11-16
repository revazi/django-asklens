"""Live settings are unreachable without both explicit live/charge consent flags."""

import os

import pytest

from django_asklens.llms import factory, openai_compatible
from django_asklens.provider_preflight import BASE_URL, MODEL
from tests.evaluation.live_support import LiveRequestBudget, live_enabled


@pytest.fixture(scope="session")
def live_request_budget():
    return LiveRequestBudget()


@pytest.fixture
def live_settings(settings, monkeypatch, live_request_budget):
    if not live_enabled(os.environ):
        pytest.skip(
            "Live tests require explicit network/charge consent and serial mode."
        )
    # Only read the dedicated live credentials after consent; never print them.
    api_key = os.environ.get("DJANGO_ASKLENS_LIVE_LLM_API_KEY")
    model = os.environ.get("DJANGO_ASKLENS_LIVE_LLM_MODEL", MODEL)
    base_url = os.environ.get("DJANGO_ASKLENS_LIVE_LLM_BASE_URL", BASE_URL)
    if (
        not api_key
        or len(api_key) > 512
        or any(not 33 <= ord(char) <= 126 for char in api_key)
        or model != MODEL
        or base_url != BASE_URL
    ):
        pytest.skip("Live provider configuration missing or invalid; no request made.")
    settings.DJANGO_ASKLENS = {
        "LLM_BACKEND": "openai_compatible",
        "LLM_BASE_URL": BASE_URL,
        "LLM_API_KEY": api_key,
        "LLM_MODEL": MODEL,
        "LLM_TIMEOUT_SECONDS": 30,
        "LLM_TEMPERATURE": 0,
        "LOG_LLM_IO": False,
        "AUDIT_INCLUDE_CONTENT": False,
        "MAX_ROWS": 50,
        "MAX_JOINS": 2,
        "MAX_METRICS": 5,
        "MAX_GROUP_BY": 3,
    }
    transport = live_request_budget.transport()
    monkeypatch.setattr(openai_compatible, "should_log_llm_io", lambda: False)
    monkeypatch.setattr(
        factory,
        "get_openai_compatible_provider",
        lambda: openai_compatible.OpenAICompatibleProvider(
            base_url=BASE_URL,
            api_key=api_key,
            model=MODEL,
            timeout_seconds=30,
            urlopen_func=transport,
        ),
    )
