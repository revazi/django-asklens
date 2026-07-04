"""LLM provider protocol for structured QueryPlan generation."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol, TypedDict


class LLMMessage(TypedDict):
    """Provider message sent to an LLM backend."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLMProvider(Protocol):
    """Provider capable of returning JSON-compatible data for a schema."""

    def complete_json(
        self,
        *,
        messages: Sequence[LLMMessage],
        schema: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Return a JSON-compatible object matching the requested schema."""
