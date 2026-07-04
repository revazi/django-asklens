"""Deterministic provider used by tests and local demos."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from django_asklens.exceptions import LLMProviderError
from django_asklens.llms.base import LLMMessage
from django_asklens.settings import get_asklens_setting

type PlanPayload = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class DummyProvider:
    """Return preconfigured QueryPlan payloads without network calls."""

    plans: Mapping[str, PlanPayload] = field(default_factory=dict)
    default_plan: PlanPayload | None = None

    def complete_json(
        self,
        *,
        messages: Sequence[LLMMessage],
        schema: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Return a deterministic plan for the latest user question."""

        question = extract_question(messages)
        if question in self.plans:
            return copy_plan_payload(self.plans[question])
        if self.default_plan is not None:
            return copy_plan_payload(self.default_plan)

        msg = f"DummyProvider has no plan configured for question {question!r}."
        raise LLMProviderError(msg)


def get_llm_provider() -> DummyProvider:
    """Return the configured provider instance.

    Phase 5 intentionally supports only the deterministic dummy backend. Real
    network providers require explicit approval in a later phase.
    """

    backend = get_asklens_setting("LLM_BACKEND")
    if backend == "dummy":
        return DummyProvider(
            plans=get_dummy_plans_setting(),
            default_plan=get_asklens_setting("DUMMY_DEFAULT_PLAN"),
        )

    msg = f"Unsupported LLM_BACKEND {backend!r}; only 'dummy' is available."
    raise LLMProviderError(msg)


def get_dummy_plans_setting() -> Mapping[str, PlanPayload]:
    """Return deterministic dummy plans configured in Django settings."""

    plans = get_asklens_setting("DUMMY_PLANS")
    if not isinstance(plans, Mapping):
        msg = "DJANGO_ASKLENS['DUMMY_PLANS'] must be a mapping."
        raise LLMProviderError(msg)
    return plans


def extract_question(messages: Sequence[LLMMessage]) -> str:
    """Extract the question from planner messages."""

    for message in messages:
        if message["role"] == "user":
            return message["content"]
    msg = "DummyProvider requires at least one user message."
    raise LLMProviderError(msg)


def copy_plan_payload(payload: PlanPayload) -> dict[str, Any]:
    """Return a deep copied mutable dict for downstream validation."""

    return dict(deepcopy(payload))
