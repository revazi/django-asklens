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

The provider sends a request to:

```text
POST {LLM_BASE_URL}/chat/completions
```

It requests strict JSON output with the QueryPlan JSON schema using OpenAI-compatible `response_format={"type": "json_schema", ...}`.

## Provider interface

Providers implement the `LLMProvider` protocol:

```python
class LLMProvider(Protocol):
    def complete_json(self, *, messages: Sequence[LLMMessage], schema: Mapping[str, Any]) -> Mapping[str, Any]:
        ...
```

AskLens sends:

- permission-scoped safe catalog metadata,
- the user's question,
- the strict `QueryPlan` JSON schema.

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

Live provider output must still pass the same strict QueryPlan parsing and catalog validation as dummy output. Before public alpha, run the [private real-project integration](private-integration.md) plan against a real multi-tenant project.

## Safety notes

- Provider output is untrusted.
- QueryPlan validation remains mandatory.
- Never execute provider-generated SQL.
- Do not send sample rows to providers by default.
- Errors are raised as `LLMProviderError` without including API keys or raw credentials.
