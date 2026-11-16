"""Default-off, standalone synthetic OpenAI probe; never bootstrap a Django host."""

import argparse
import json
import math
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

from django_asklens.llms.openai_compatible import (
    build_chat_completions_request,
    extract_message_content,
    parse_json_content,
)

BASE_URL = "https://api.openai.com/v1"
MODEL = "gpt-4.1-mini-2025-04-14"
API_KEY_ENV = "DJANGO_ASKLENS_PREFLIGHT_API_KEY"
MAX_RESPONSE_BYTES = 16_384
MAX_COMPLETION_TOKENS = 32
DISCLOSURE = (
    "Synthetic preflight: with --allow-network-and-charges this sends ONE HTTPS "
    "request to OpenAI and may incur charges. No application data is used. "
    "Request/token limits are NOT financial caps. Live acceptance is UNVERIFIED."
)


class _InvalidArguments(Exception):
    """Keep argparse from echoing potentially secret-bearing arguments."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _InvalidArguments


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward Authorization or turn one operation into another request.
        return None


def _probe(*, api_key: str, timeout: float) -> str:
    """Compose existing provider primitives without settings-backed I/O logging.

    Deliberately do not call complete_json/send_json_request: those consult host
    settings and can log provider bodies. This isolated opener has no ambient
    proxies, redirects, retries, cookies, or global installed-opener state.
    """

    request = build_chat_completions_request(
        base_url=BASE_URL,
        api_key=api_key,
        model=MODEL,
        temperature=0,
        messages=(
            {"role": "system", "content": "Return only the fixed synthetic JSON."},
            {"role": "user", "content": 'Return {"probe":"ok"}.'},
        ),
        schema={
            "title": "AskLensSyntheticProbe",
            "type": "object",
            "properties": {"probe": {"type": "string", "enum": ["ok"]}},
            "required": ["probe"],
            "additionalProperties": False,
        },
    )
    payload = json.loads(request.data)
    payload.update(
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        n=1,
        stream=False,
    )
    request.data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        # Never read, log, serialize or retain an HTTP error body, URL or reason.
        code = exc.code
        exc.close()
        if code in {401, 403}:
            return "authentication_rejected"
        if code == 429:
            return "rate_limited"
        if code in {400, 422}:
            return "schema_or_request_rejected"
        if code in {301, 302, 303, 307, 308}:
            return "redirect_rejected"
        return "provider_failed"
    except TimeoutError:
        return "timed_out"
    except URLError as exc:
        return "timed_out" if isinstance(exc.reason, TimeoutError) else "network_failed"

    if len(body) > MAX_RESPONSE_BYTES:
        return "invalid_output"
    try:
        envelope = json.loads(body)
        choice = envelope["choices"][0]
        if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
            return "invalid_output"
        content = parse_json_content(extract_message_content(envelope))
        if content != {"probe": "ok"}:
            return "invalid_output"
    except Exception:  # noqa: BLE001 - untrusted output never escapes this boundary
        return "invalid_output"
    return "synthetic_ok"


def _emit(code: str, *, timeout: float | None = None) -> int:
    """Emit only fixed metadata, never caller input or provider content."""

    passed = code == "synthetic_ok"
    result = {"status": "passed" if passed else "not_passed", "code": code}
    if passed:
        result.update(
            provider="OpenAI",
            scope="synthetic_only",
            application_acceptance="incomplete",
            model=MODEL,
            base_url=BASE_URL,
            observed_at=datetime.now(UTC).isoformat(),
            timeout_seconds=timeout,
            max_requests=1,
            concurrency=1,
            max_completion_tokens=MAX_COMPLETION_TOKENS,
            temperature=0,
            retries=0,
        )
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if passed else 2


def main(argv: Sequence[str] | None = None) -> int:
    """Require per-invocation consent before reading the dedicated key or HTTP."""

    print(DISCLOSURE, flush=True)
    parser = _Parser(
        prog="python -m django_asklens.provider_preflight",
        allow_abbrev=False,
        description=(
            "Fixed synthetic probe only; no Django setup, settings, registry access "
            "or application SQL. Uses the dedicated " + API_KEY_ENV + " variable. "
            "No endpoint, model, prompt or schema overrides are supported."
        ),
    )
    parser.add_argument("--allow-network-and-charges", action="store_true")
    parser.add_argument("--timeout-seconds", default="30", metavar="SECONDS")
    try:
        args = parser.parse_args(argv)
        if not args.allow_network_and_charges:
            return _emit("consent_required")
        try:
            timeout = float(args.timeout_seconds)
        except (ValueError, OverflowError):
            return _emit("invalid_configuration")
        if not math.isfinite(timeout) or not 1 <= timeout <= 30:
            return _emit("invalid_configuration")
        # No ambient OPENAI_API_KEY, Django settings or live-test flag is consent.
        api_key = os.environ.get(API_KEY_ENV)
        if (
            not api_key
            or len(api_key) > 512
            or any(not 33 <= ord(char) <= 126 for char in api_key)
        ):
            return _emit("invalid_configuration")
        return _emit(_probe(api_key=api_key, timeout=timeout), timeout=timeout)
    except _InvalidArguments:
        return _emit("invalid_arguments")
    except KeyboardInterrupt:
        return _emit("interrupted")
    except Exception:  # noqa: BLE001 - no raw exception/cause or traceback on stderr
        return _emit("probe_failed")


if __name__ == "__main__":
    raise SystemExit(main())
