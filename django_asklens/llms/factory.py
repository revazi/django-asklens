"""LLM provider factory."""

from django_asklens.exceptions import LLMProviderError
from django_asklens.llms.base import LLMProvider
from django_asklens.llms.dummy import DummyProvider, get_dummy_plans_setting
from django_asklens.llms.openai_compatible import get_openai_compatible_provider
from django_asklens.settings import get_asklens_setting


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider instance."""

    backend = get_asklens_setting("LLM_BACKEND")
    if backend == "dummy":
        return DummyProvider(
            plans=get_dummy_plans_setting(),
            default_plan=get_asklens_setting("DUMMY_DEFAULT_PLAN"),
        )
    if backend == "openai_compatible":
        return get_openai_compatible_provider()

    msg = (
        f"Unsupported LLM_BACKEND {backend!r}; expected 'dummy' or 'openai_compatible'."
    )
    raise LLMProviderError(msg)
