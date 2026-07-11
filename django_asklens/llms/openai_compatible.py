"""OpenAI-compatible LLM provider using Python stdlib HTTP."""

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django_asklens.exceptions import LLMProviderError
from django_asklens.llms.base import LLMMessage
from django_asklens.settings import get_asklens_setting

type UrlOpen = Callable[..., Any]

logger = logging.getLogger("django_asklens.llms.openai_compatible")


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProvider:
    """Provider for OpenAI-compatible chat-completions JSON APIs."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 30
    temperature: float = 0
    urlopen_func: UrlOpen = urlopen

    def __post_init__(self) -> None:
        validate_provider_config(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )

    def complete_json(
        self,
        *,
        messages: Sequence[LLMMessage],
        schema: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Return a JSON object from an OpenAI-compatible provider."""

        request = build_chat_completions_request(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            schema=schema,
            temperature=self.temperature,
        )
        log_llm_request(request)
        response_payload = send_json_request(
            request,
            timeout_seconds=self.timeout_seconds,
            urlopen_func=self.urlopen_func,
        )
        log_llm_response(response_payload)
        content = extract_message_content(response_payload)
        parsed_content = parse_json_content(content)
        log_llm_parsed_content(parsed_content)
        return parsed_content


def log_llm_request(request: Request) -> None:
    """Log the sanitized outbound provider request when explicitly enabled."""

    if not should_log_llm_io():
        return
    logger.info(
        "AskLens LLM request: %s",
        json.dumps(sanitize_request_for_logging(request), indent=2, sort_keys=True),
    )


def log_llm_response(response_payload: Mapping[str, Any]) -> None:
    """Log the raw provider response payload when explicitly enabled."""

    if not should_log_llm_io():
        return
    logger.info(
        "AskLens LLM response: %s",
        json.dumps(response_payload, indent=2, sort_keys=True),
    )


def log_llm_http_error(status_code: int, body: str) -> None:
    """Log a provider HTTP error body when explicitly enabled."""

    if not should_log_llm_io():
        return
    logger.info(
        "AskLens LLM HTTP error: %s",
        json.dumps(
            {"status_code": status_code, "body": body}, indent=2, sort_keys=True
        ),
    )


def log_llm_parsed_content(parsed_content: Mapping[str, Any]) -> None:
    """Log the parsed JSON content returned by the provider."""

    if not should_log_llm_io():
        return
    logger.info(
        "AskLens LLM parsed JSON: %s",
        json.dumps(parsed_content, indent=2, sort_keys=True),
    )


def read_http_error_body(exc: HTTPError) -> str:
    """Return a provider HTTP error body as safe text for opt-in logs."""

    try:
        body = exc.read()
    except Exception:  # noqa: BLE001 - best-effort logging helper
        return ""
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return "<non-utf8 error body>"


def sanitize_request_for_logging(request: Request) -> dict[str, Any]:
    """Return request details without credentials or authorization headers."""

    headers = {
        name: value
        for name, value in request.header_items()
        if name.lower() != "authorization"
    }
    body: Any = None
    if request.data:
        try:
            body = json.loads(request.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = "<non-json request body>"
    return {
        "method": request.get_method(),
        "url": request.full_url,
        "headers": headers,
        "body": body,
    }


def should_log_llm_io() -> bool:
    """Return whether provider request/response logging is enabled."""

    return bool(get_asklens_setting("LOG_LLM_IO"))


def get_openai_compatible_provider() -> OpenAICompatibleProvider:
    """Build a provider from Django AskLens settings."""

    return OpenAICompatibleProvider(
        base_url=get_string_setting("LLM_BASE_URL"),
        api_key=get_string_setting("LLM_API_KEY"),
        model=get_string_setting("LLM_MODEL"),
        timeout_seconds=get_positive_number_setting("LLM_TIMEOUT_SECONDS"),
        temperature=get_number_setting("LLM_TEMPERATURE"),
    )


def build_chat_completions_request(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: Sequence[LLMMessage],
    schema: Mapping[str, Any],
    temperature: float,
) -> Request:
    """Build a stdlib HTTP request for a chat-completions JSON call."""

    payload = {
        "model": model,
        "messages": [dict(message) for message in messages],
        "temperature": temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": str(schema.get("title") or "QueryPlan"),
                "schema": dict(schema),
                "strict": True,
            },
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return Request(
        url=chat_completions_url(base_url),
        data=body,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def send_json_request(
    request: Request,
    *,
    timeout_seconds: float,
    urlopen_func: UrlOpen,
) -> Mapping[str, Any]:
    """Send one JSON HTTP request and parse the JSON response body."""

    try:
        with urlopen_func(request, timeout=timeout_seconds) as response:
            body = response.read()
    except HTTPError as exc:
        error_body = read_http_error_body(exc)
        log_llm_http_error(exc.code, error_body)
        msg = f"LLM provider request failed with HTTP status {exc.code}."
        raise LLMProviderError(msg) from exc
    except URLError as exc:
        msg = "LLM provider request failed."
        raise LLMProviderError(msg) from exc
    except TimeoutError as exc:
        msg = "LLM provider request timed out."
        raise LLMProviderError(msg) from exc

    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        msg = "LLM provider response body was not valid JSON."
        raise LLMProviderError(msg) from exc
    if not isinstance(parsed, Mapping):
        msg = "LLM provider response body must be a JSON object."
        raise LLMProviderError(msg)
    return parsed


def extract_message_content(response_payload: Mapping[str, Any]) -> str:
    """Extract the assistant message content from a chat-completions response."""

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        msg = "LLM provider response did not include choices."
        raise LLMProviderError(msg)

    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        msg = "LLM provider response choice must be an object."
        raise LLMProviderError(msg)

    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        msg = "LLM provider response choice did not include a message object."
        raise LLMProviderError(msg)

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        msg = "LLM provider response message content must be a non-empty string."
        raise LLMProviderError(msg)
    return content


def parse_json_content(content: str) -> Mapping[str, Any]:
    """Parse assistant content as a JSON object."""

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        msg = "LLM provider message content was not valid JSON."
        raise LLMProviderError(msg) from exc
    if not isinstance(parsed, Mapping):
        msg = "LLM provider message content must be a JSON object."
        raise LLMProviderError(msg)
    return parsed


def chat_completions_url(base_url: str) -> str:
    """Return the chat completions endpoint URL."""

    return f"{base_url.rstrip('/')}/chat/completions"


def validate_provider_config(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: float,
) -> None:
    """Validate provider configuration without exposing secrets."""

    if not base_url:
        msg = "DJANGO_ASKLENS['LLM_BASE_URL'] is required for openai_compatible."
        raise LLMProviderError(msg)
    if not api_key:
        msg = "DJANGO_ASKLENS['LLM_API_KEY'] is required for openai_compatible."
        raise LLMProviderError(msg)
    if not model:
        msg = "DJANGO_ASKLENS['LLM_MODEL'] is required for openai_compatible."
        raise LLMProviderError(msg)
    if timeout_seconds <= 0:
        msg = "DJANGO_ASKLENS['LLM_TIMEOUT_SECONDS'] must be positive."
        raise LLMProviderError(msg)


def get_string_setting(name: str) -> str:
    """Return one non-empty string AskLens setting."""

    value = get_asklens_setting(name)
    if not isinstance(value, str) or not value.strip():
        msg = f"DJANGO_ASKLENS[{name!r}] must be a non-empty string."
        raise LLMProviderError(msg)
    return value.strip()


def get_number_setting(name: str) -> float:
    """Return one numeric AskLens setting."""

    value = get_asklens_setting(name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        msg = f"DJANGO_ASKLENS[{name!r}] must be numeric."
        raise LLMProviderError(msg)
    return float(value)


def get_positive_number_setting(name: str) -> float:
    """Return one positive numeric AskLens setting."""

    value = get_number_setting(name)
    if value <= 0:
        msg = f"DJANGO_ASKLENS[{name!r}] must be positive."
        raise LLMProviderError(msg)
    return value
