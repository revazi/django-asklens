"""Synthetic-only preflight privacy, isolation, consent and transport regressions."""

import io
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener
from urllib.response import addinfourl

import pytest

from django_asklens import provider_preflight as probe
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.llms import openai_compatible

CANARY = "synthetic-sensitive-canary"
CONSENT = ["--allow-network-and-charges"]


def envelope(content='{"probe":"ok"}', **extra):
    return json.dumps(
        {
            "choices": [
                {"finish_reason": "stop", "message": {"content": content, **extra}}
            ]
        }
    ).encode()


class Response(io.BytesIO):
    def read(self, size=-1):
        assert size == probe.MAX_RESPONSE_BYTES + 1
        return super().read(size)


@pytest.fixture
def isolated(monkeypatch, settings):
    """Even an opted-in probe must not consult settings/catalog or log I/O."""

    settings.DJANGO_ASKLENS = {"LOG_LLM_IO": True}
    monkeypatch.setenv(probe.API_KEY_ENV, CANARY)

    def forbidden(*args, **kwargs):
        raise AssertionError("Application/settings/logging access is forbidden")

    for name in ("register", "get", "all", "clear", "to_dict"):
        monkeypatch.setattr(CatalogRegistry, name, forbidden)
    for name in (
        "get_asklens_setting",
        "should_log_llm_io",
        "log_llm_request",
        "log_llm_response",
        "log_llm_http_error",
        "log_llm_parsed_content",
    ):
        monkeypatch.setattr(openai_compatible, name, forbidden)
    calls = []
    state = SimpleNamespace(body=envelope(), error=None)

    def open_request(request, *, timeout):
        calls.append((request, timeout))
        if state.error:
            raise state.error
        return Response(state.body)

    def opener(*handlers):
        assert any(isinstance(h, probe._NoRedirect) for h in handlers)
        assert next(h for h in handlers if isinstance(h, ProxyHandler)).proxies == {}
        return SimpleNamespace(open=open_request)

    monkeypatch.setattr(probe, "build_opener", opener)
    return calls, state


def result(capsys, caplog):
    captured = capsys.readouterr()
    assert captured.out.startswith(probe.DISCLOSURE + "\n")
    assert captured.err == ""
    assert CANARY not in captured.out + captured.err + caplog.text
    assert not caplog.records
    return json.loads(captured.out.splitlines()[-1])


def test_fixed_synthetic_request_and_prior_disclosure(isolated, capsys, caplog):
    calls, _ = isolated
    assert probe.main(CONSENT) == 0
    output = result(capsys, caplog)
    assert output["code"] == "synthetic_ok"
    assert output["model"] == probe.MODEL
    assert output["max_requests"] == output["concurrency"] == 1
    assert output["retries"] == 0
    assert output["observed_at"].endswith("+00:00")
    assert len(calls) == 1
    request, timeout = calls[0]
    assert timeout == 30
    assert request.full_url == probe.BASE_URL + "/chat/completions"
    payload = json.loads(request.data)
    assert payload == {
        "model": probe.MODEL,
        "messages": [
            {"role": "system", "content": "Return only the fixed synthetic JSON."},
            {"role": "user", "content": 'Return {"probe":"ok"}.'},
        ],
        "temperature": 0,
        "max_completion_tokens": 32,
        "n": 1,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "AskLensSyntheticProbe",
                "strict": True,
                "schema": {
                    "title": "AskLensSyntheticProbe",
                    "type": "object",
                    "properties": {"probe": {"type": "string", "enum": ["ok"]}},
                    "required": ["probe"],
                    "additionalProperties": False,
                },
            },
        },
    }


@pytest.mark.parametrize("timeout", ["1", "10", "30"])
def test_valid_timeout_reaches_only_mocked_transport(timeout, isolated, capsys, caplog):
    calls, _ = isolated
    assert probe.main([*CONSENT, "--timeout-seconds", timeout]) == 0
    assert result(capsys, caplog)["timeout_seconds"] == float(timeout)
    assert len(calls) == 1
    assert calls[0][1] == float(timeout)


def test_help_is_offline_even_with_consent_flag(isolated, capsys):
    calls, _ = isolated
    with pytest.raises(SystemExit) as exc:
        probe.main([*CONSENT, "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert probe.DISCLOSURE in captured.out
    assert CANARY not in captured.out + captured.err
    assert captured.err == ""
    assert calls == []


def test_disclosure_is_flushed_before_transport(isolated, monkeypatch, capsys):
    def opener(*handlers):
        assert capsys.readouterr().out.startswith(probe.DISCLOSURE)
        raise RuntimeError(CANARY)

    monkeypatch.setattr(probe, "build_opener", opener)
    assert probe.main(CONSENT) == 2
    assert CANARY not in capsys.readouterr().out


def test_no_consent_never_reads_key_or_connects(isolated, monkeypatch, capsys, caplog):
    calls, _ = isolated

    class NoEnvironment:
        def get(self, key):
            raise AssertionError("Environment must not be read without consent")

    monkeypatch.setattr(probe, "os", SimpleNamespace(environ=NoEnvironment()))
    assert probe.main([]) == 2
    assert result(capsys, caplog)["code"] == "consent_required"
    assert calls == []


@pytest.mark.parametrize("key", [None, "", " ", "key\n" + CANARY, "é", "x" * 513])
def test_missing_or_invalid_key_rejected_offline(
    key, isolated, monkeypatch, capsys, caplog
):
    calls, _ = isolated
    if key is None:
        monkeypatch.delenv(probe.API_KEY_ENV)
    else:
        monkeypatch.setenv(probe.API_KEY_ENV, key)
    assert probe.main(CONSENT) == 2
    assert result(capsys, caplog)["code"] == "invalid_configuration"
    assert calls == []


@pytest.mark.parametrize("timeout", ["nan", "inf", "-inf", "0", "-1", "31", CANARY])
def test_timeout_is_finite_and_bounded(timeout, isolated, capsys, caplog):
    calls, _ = isolated
    assert probe.main([*CONSENT, "--timeout-seconds", timeout]) == 2
    assert result(capsys, caplog)["code"] in {
        "invalid_configuration",
        "invalid_arguments",
    }
    assert calls == []


@pytest.mark.parametrize(
    "args",
    [
        [CANARY],
        ["--base-url", "https://example.test/?key=" + CANARY],
        ["--timeout-seconds"],
        ["--allow-network-and-charges=" + CANARY],
        ["--allow-network"],
    ],
)
def test_invalid_arguments_never_echo_inputs(args, isolated, capsys, caplog):
    calls, _ = isolated
    assert probe.main(args) == 2
    assert result(capsys, caplog)["code"] == "invalid_arguments"
    assert calls == []


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, "schema_or_request_rejected"),
        (422, "schema_or_request_rejected"),
        (401, "authentication_rejected"),
        (403, "authentication_rejected"),
        (429, "rate_limited"),
        (500, "provider_failed"),
        (302, "redirect_rejected"),
    ],
)
def test_sensitive_http_failure_is_opaque_and_not_retried(
    status, expected, isolated, capsys, caplog
):
    calls, state = isolated

    class Unreadable(io.BytesIO):
        def read(self, *args):
            pytest.fail("HTTP error bodies must not be read")

    body = Unreadable(CANARY.encode())
    state.error = HTTPError(
        "https://example.test/?key=" + CANARY,
        status,
        CANARY,
        {"Authorization": "Bearer " + CANARY, "Location": CANARY},
        body,
    )
    with caplog.at_level(logging.DEBUG):
        assert probe.main(CONSENT) == 2
    assert result(capsys, caplog)["code"] == expected
    assert len(calls) == 1
    assert body.closed


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TimeoutError(CANARY), "timed_out"),
        (URLError(TimeoutError(CANARY)), "timed_out"),
        (URLError(CANARY), "network_failed"),
        (RuntimeError(CANARY), "probe_failed"),
    ],
)
def test_hostile_transport_exceptions_never_escape(
    error, code, isolated, capsys, caplog
):
    calls, state = isolated
    state.error = error
    assert probe.main(CONSENT) == 2
    assert result(capsys, caplog)["code"] == code
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        CANARY.encode(),
        b"\xff",
        b"[]",
        b"{}",
        envelope(CANARY),
        envelope('{"probe":"wrong"}'),
        envelope('{"probe":"ok","secret":"' + CANARY + '"}'),
        envelope(refusal=CANARY),
        envelope().replace(b'"stop"', b'"length"'),
        b"x" * (probe.MAX_RESPONSE_BYTES + 1),
    ],
)
def test_malformed_refused_truncated_and_oversized_output_is_opaque(
    body, isolated, capsys, caplog
):
    calls, state = isolated
    state.body = body
    assert probe.main(CONSENT) == 2
    assert result(capsys, caplog)["code"] == "invalid_output"
    assert len(calls) == 1


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_handler_never_opens_second_request(status):
    handler = probe._NoRedirect()
    handler.parent = SimpleNamespace(open=lambda *a, **kw: pytest.fail("redirected"))
    request = Request(probe.BASE_URL, data=b"{}", headers={"Authorization": CANARY})
    # Returning None delegates rejection to urllib's default HTTP error handler;
    # unlike the stock redirect handler, it never calls parent.open().
    assert (
        handler.http_error_302(
            request,
            io.BytesIO(),
            status,
            CANARY,
            {"location": "https://other.test/?key=" + CANARY},
        )
        is None
    )


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_real_opener_blocks_redirect_before_a_second_exchange(
    status, isolated, monkeypatch, capsys, caplog
):
    calls = []

    def synthetic_https(handler, request):
        calls.append(request)
        response = addinfourl(
            io.BytesIO(CANARY.encode()),
            {"location": "https://other.test/?key=" + CANARY},
            request.full_url,
            status,
        )
        response.msg = CANARY
        return response

    monkeypatch.setattr(HTTPSHandler, "https_open", synthetic_https)
    monkeypatch.setattr(probe, "build_opener", build_opener)
    assert probe.main(CONSENT) == 2
    assert result(capsys, caplog)["code"] == "redirect_rejected"
    assert len(calls) == 1


def test_standalone_process_does_not_bootstrap_host(tmp_path):
    """Fresh interpreter, with a configured hostile host and no pytest Django setup."""

    root = Path(__file__).resolve().parents[2]
    (tmp_path / "hosttrap.py").write_text('raise RuntimeError("host was imported")')
    script = """
import django
import django.conf
import socket
import sys

def forbidden(*args, **kwargs):
    raise AssertionError("forbidden host/network access")
django.setup = forbidden
django.conf.LazySettings._setup = forbidden
socket.create_connection = forbidden
from django_asklens import provider_preflight as probe
from django_asklens.catalog.registry import CatalogRegistry
for name in ("register", "get", "all", "clear", "to_dict"):
    setattr(CatalogRegistry, name, forbidden)
assert probe.main([]) == 2
assert probe.main(["--allow-network-and-charges"]) == 2
# Exercise the opted-in success path with an inert transport, still no host setup.
import io
import json
import os
from types import SimpleNamespace
os.environ[probe.API_KEY_ENV] = "synthetic-test-key"
body = json.dumps({"choices": [{"finish_reason": "stop", "message": {
    "content": '{"probe":"ok"}'}}]}).encode()
probe.build_opener = lambda *handlers: SimpleNamespace(
    open=lambda *a, **kw: io.BytesIO(body))
assert probe.main(["--allow-network-and-charges"]) == 0
assert not django.conf.settings.configured
assert "hosttrap" not in sys.modules
assert "django_asklens.models" not in sys.modules
assert "django_asklens.querying" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(root) + os.pathsep + str(tmp_path),
            "DJANGO_SETTINGS_MODULE": "hosttrap",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
