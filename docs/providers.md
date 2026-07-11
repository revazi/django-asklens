# Provider configuration

AskLens treats provider output as untrusted data. A provider may suggest a structured `QueryPlan`, but AskLens validates it before compilation or execution.

## Default backend: dummy

The default backend is deterministic and local:

```python
DJANGO_ASKLENS = {
    "LLM_BACKEND": "dummy",
    "DUMMY_PLANS": {
        "Show orders by status": {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            "limit": 100,
            "visualization": {"type": "bar", "x": "status", "y": "order_count"},
        }
    },
    "DUMMY_DEFAULT_PLAN": None,
}
```

`DummyProvider` makes no network calls and requires no API keys. Tests and evaluation fixtures should use it by default.

## OpenAI-compatible backend

Phase 10 adds an OpenAI-compatible chat-completions provider implemented with Python stdlib HTTP. It adds no required runtime dependency.

```python
import os

DJANGO_ASKLENS = {
    "LLM_BACKEND": "openai_compatible",
    "LLM_BASE_URL": "https://api.openai.com/v1",
    "LLM_API_KEY": os.environ["OPENAI_API_KEY"],
    "LLM_MODEL": "gpt-4.1-mini",
    "LLM_TIMEOUT_SECONDS": 30,
    "LLM_TEMPERATURE": 0,
}
```

Use environment variables or your deployment secret manager for `LLM_API_KEY`. Do not commit API keys or place them in docs, fixtures, or tests.

For local prompt/provider tuning, you can temporarily enable provider I/O logging:

```python
DJANGO_ASKLENS = {
    # ...
    "LOG_LLM_IO": True,
}
```

This logs the outbound chat-completions request body, raw provider response, and parsed JSON content to the `django_asklens.llms.openai_compatible` logger at `INFO` level. Authorization headers and API keys are excluded. Treat these logs as sensitive anyway: they can include user questions, permission-scoped schema/capabilities metadata, and provider-generated plans/help. Do not enable this in production unless your logging pipeline is approved for that data.

The provider sends a request to:

```text
POST {LLM_BASE_URL}/chat/completions
```

For normal live `/asklens/query/` calls, it requests strict JSON output with a unified AskLens provider-response schema using OpenAI-compatible `response_format={"type": "json_schema", ...}`. That single response chooses either a data `QueryPlan` or capability `QueryHelp`. Other lower-level planner/helper APIs may request their narrower schemas directly.

## Provider interface

Providers implement the `LLMProvider` protocol:

```python
class LLMProvider(Protocol):
    def complete_json(self, *, messages: Sequence[LLMMessage], schema: Mapping[str, Any]) -> Mapping[str, Any]:
        ...
```

AskLens sends:

- permission-scoped safe capabilities or catalog metadata,
- the user's question,
- a strict JSON schema for the response being requested.

AskLens must not send sample database rows, secrets, credentials, `.env` content, or unregistered/unauthorized sensitive fields by default.

## Testing live providers

Default tests never call live providers and require no API keys.

Run the opt-in live smoke test only when you explicitly want to test a configured provider:

```bash
DJANGO_ASKLENS_LIVE_LLM=1 \
DJANGO_ASKLENS_LIVE_LLM_API_KEY="$OPENAI_API_KEY" \
DJANGO_ASKLENS_LIVE_LLM_MODEL="gpt-4.1-mini" \
uv run pytest tests/evaluation/test_live_openai_compatible.py \
  tests/evaluation/test_live_api_openai_compatible.py
```

Optional:

```bash
DJANGO_ASKLENS_LIVE_LLM_BASE_URL="https://api.openai.com/v1"
```

The runnable complex demo project can also use the live provider by setting `DJANGO_ASKLENS_DEMO_LIVE_LLM=1` before starting `tests.test_project.demo_settings`. See [Runnable complex test project](test-project-demo.md).

Live provider output must still pass strict schema parsing plus catalog/permission validation. Unified live query responses validate either the returned `QueryPlan` or the returned `QueryHelp` suggestions; help suggestions get executable plans synthesized and validated locally. Before public alpha, run the [private real-project integration](private-integration.md) plan against a real multi-tenant project.

## Safety notes

- Provider output is untrusted.
- QueryPlan validation remains mandatory.
- Never execute provider-generated SQL.
- Do not send sample rows to providers by default.
- Errors and opt-in provider I/O logs exclude API keys and authorization headers.
