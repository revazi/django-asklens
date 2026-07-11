"""Tests for the OpenAI-compatible provider."""

import json
import logging
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError

import pytest

from django_asklens.exceptions import LLMProviderError
from django_asklens.llms import OpenAICompatibleProvider, get_llm_provider
from django_asklens.llms.openai_compatible import (
    build_chat_completions_request,
    chat_completions_url,
    extract_message_content,
    parse_json_content,
)
from django_asklens.planning.schemas import get_query_plan_json_schema


class FakeResponse:
    """Context-manager response for stdlib urlopen tests."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class RecordingUrlOpen:
    """Record request details and return a configured JSON payload."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload
        self.request = None
        self.timeout = None

    def __call__(self, request, *, timeout: float):
        self.request = request
        self.timeout = timeout
        return FakeResponse(self.payload)


def provider_response(content: Mapping[str, Any]) -> dict[str, Any]:
    """Return an OpenAI-compatible chat response payload."""

    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def test_openai_compatible_provider_sends_schema_request_and_parses_json() -> None:
    recorder = RecordingUrlOpen(
        provider_response(
            {
                "resource": "orders",
                "intent": "aggregate",
                "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            }
        )
    )
    provider = OpenAICompatibleProvider(
        base_url="https://llm.example/v1/",
        api_key="secret-test-key",
        model="test-model",
        timeout_seconds=12,
        urlopen_func=recorder,
    )

    result = provider.complete_json(
        messages=({"role": "user", "content": "Show orders"},),
        schema=get_query_plan_json_schema(),
    )

    assert result["resource"] == "orders"
    assert recorder.timeout == 12
    assert recorder.request is not None
    assert recorder.request.full_url == "https://llm.example/v1/chat/completions"
    headers = dict(recorder.request.header_items())
    assert headers["Authorization"] == "Bearer secret-test-key"
    assert headers["Content-type"] == "application/json"

    request_payload = json.loads(recorder.request.data.decode("utf-8"))
    assert request_payload["model"] == "test-model"
    assert request_payload["messages"] == [{"role": "user", "content": "Show orders"}]
    assert request_payload["response_format"]["type"] == "json_schema"
    assert request_payload["response_format"]["json_schema"]["schema"]["title"] == (
        "QueryPlan"
    )
    assert request_payload["response_format"]["json_schema"]["strict"] is True


def test_openai_provider_logs_request_and_response_when_enabled(
    settings, caplog
) -> None:
    """Opt-in logs expose provider I/O without API keys."""

    settings.DJANGO_ASKLENS = {"LOG_LLM_IO": True}
    recorder = RecordingUrlOpen(
        provider_response(
            {
                "resource": "orders",
                "intent": "aggregate",
                "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            }
        )
    )
    provider = OpenAICompatibleProvider(
        base_url="https://llm.example/v1/",
        api_key="secret-test-key",
        model="test-model",
        timeout_seconds=12,
        urlopen_func=recorder,
    )

    with caplog.at_level(
        logging.INFO,
        logger="django_asklens.llms.openai_compatible",
    ):
        provider.complete_json(
            messages=({"role": "user", "content": "Show orders"},),
            schema=get_query_plan_json_schema(),
        )

    log_text = caplog.text
    assert "AskLens LLM request" in log_text
    assert "AskLens LLM response" in log_text
    assert "AskLens LLM parsed JSON" in log_text
    assert "Show orders" in log_text
    assert "order_count" in log_text
    assert "secret-test-key" not in log_text
    assert "Authorization" not in log_text


def test_openai_provider_factory_uses_settings(settings) -> None:
    settings.DJANGO_ASKLENS = {
        "LLM_BACKEND": "openai_compatible",
        "LLM_BASE_URL": "https://llm.example/v1",
        "LLM_API_KEY": "secret-test-key",
        "LLM_MODEL": "test-model",
        "LLM_TIMEOUT_SECONDS": 9,
    }

    provider = get_llm_provider()

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "https://llm.example/v1"
    assert provider.model == "test-model"
    assert provider.timeout_seconds == 9


def test_openai_provider_requires_key_and_model(settings) -> None:
    settings.DJANGO_ASKLENS = {
        "LLM_BACKEND": "openai_compatible",
        "LLM_API_KEY": "secret-test-key",
        "LLM_MODEL": None,
    }

    with pytest.raises(LLMProviderError, match="LLM_MODEL"):
        get_llm_provider()

    settings.DJANGO_ASKLENS = {
        "LLM_BACKEND": "openai_compatible",
        "LLM_API_KEY": None,
        "LLM_MODEL": "test-model",
    }

    with pytest.raises(LLMProviderError, match="LLM_API_KEY"):
        get_llm_provider()


def test_openai_provider_errors_do_not_leak_api_key() -> None:
    def failing_urlopen(request, *, timeout: float):
        raise HTTPError(
            url=request.full_url,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

    provider = OpenAICompatibleProvider(
        base_url="https://llm.example/v1",
        api_key="secret-test-key",
        model="test-model",
        urlopen_func=failing_urlopen,
    )

    with pytest.raises(LLMProviderError) as exc_info:
        provider.complete_json(
            messages=({"role": "user", "content": "Show orders"},),
            schema=get_query_plan_json_schema(),
        )

    error = str(exc_info.value)
    assert "401" in error
    assert "secret-test-key" not in error


def test_openai_response_shape_validation() -> None:
    with pytest.raises(LLMProviderError, match="choices"):
        extract_message_content({})

    with pytest.raises(LLMProviderError, match="valid JSON"):
        parse_json_content("not-json")

    with pytest.raises(LLMProviderError, match="JSON object"):
        parse_json_content("[]")


def test_chat_completions_url_strips_trailing_slash() -> None:
    assert chat_completions_url("https://llm.example/v1/") == (
        "https://llm.example/v1/chat/completions"
    )


def test_build_chat_completions_request_does_not_mutate_inputs() -> None:
    messages = ({"role": "user", "content": "Show orders"},)
    schema = get_query_plan_json_schema()

    request = build_chat_completions_request(
        base_url="https://llm.example/v1",
        api_key="secret-test-key",
        model="test-model",
        messages=messages,
        schema=schema,
        temperature=0,
    )

    payload = json.loads(request.data.decode("utf-8"))
    assert payload["messages"] == [{"role": "user", "content": "Show orders"}]
    assert schema["title"] == "QueryPlan"
