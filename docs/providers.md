# Provider configuration

AskLens treats provider output as untrusted data. A provider may suggest a structured `QueryPlan`, but AskLens validates it before compilation or execution.

## Current backend: dummy

The only built-in MVP backend is deterministic and local:

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

## Provider interface

Future providers should implement the `LLMProvider` protocol:

```python
class LLMProvider(Protocol):
    def complete_json(self, *, messages: Sequence[LLMMessage], schema: Mapping[str, Any]) -> Mapping[str, Any]:
        ...
```

AskLens sends:

- safe catalog metadata,
- the user's question,
- the strict `QueryPlan` JSON schema.

AskLens must not send sample database rows, secrets, credentials, `.env` content, or unregistered/sensitive fields by default.

## Live provider requirements

A future live adapter should be explicitly approved before implementation. It should include:

- opt-in settings,
- no default test network calls,
- API-key handling through host-project settings/environment,
- timeout/error handling,
- prompt content review,
- tests proving sensitive fields and sample rows are excluded.

Live provider output must still pass the same strict QueryPlan parsing and catalog validation as dummy output.
