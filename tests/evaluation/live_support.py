"""Consent and single-process request bounds for deliberately opted-in tests."""

import json
import os
from collections.abc import Mapping
from contextlib import contextmanager
from threading import Lock
from urllib.request import ProxyHandler, build_opener

from django_asklens.exceptions import LLMProviderError
from django_asklens.provider_preflight import BASE_URL, MODEL, _NoRedirect

CONSENT = "network-and-charges"
MAX_REQUESTS = 7
MAX_COMPLETION_TOKENS = 2048


def live_enabled(environ: Mapping[str, str]) -> bool:
    return (
        environ.get("DJANGO_ASKLENS_LIVE_LLM") == "1"
        and environ.get("DJANGO_ASKLENS_LIVE_LLM_CONSENT") == CONSENT
        and not environ.get("PYTEST_XDIST_WORKER")
    )


class LiveRequestBudget:
    """At most seven serial requests/session and one request/test, no redirects."""

    def __init__(self):
        self.count = 0
        self.lock = Lock()

    def transport(self):
        used = False

        @contextmanager
        def open_once(request, *, timeout):
            nonlocal used
            if not live_enabled(os.environ) or not self.lock.acquire(blocking=False):
                raise LLMProviderError(
                    "Live test consent or serial execution required."
                )
            try:
                if used or self.count >= MAX_REQUESTS:
                    raise LLMProviderError("Live test request limit reached.")
                if request.full_url != BASE_URL + "/chat/completions" or timeout != 30:
                    raise LLMProviderError("Live test configuration rejected.")
                payload = json.loads(request.data)
                if payload.get("model") != MODEL:
                    raise LLMProviderError("Live test configuration rejected.")
                payload.update(max_completion_tokens=MAX_COMPLETION_TOKENS, n=1)
                request.data = json.dumps(payload).encode()
                used = True
                self.count += 1
                opener = build_opener(ProxyHandler({}), _NoRedirect())
                with opener.open(request, timeout=timeout) as response:
                    yield response
            except Exception:
                # Suppress raw transport, response, and provider parse exceptions.
                raise LLMProviderError("Live test provider operation failed.") from None
            finally:
                self.lock.release()

        return open_once
