"""Settings helpers for Django AskLens."""

from collections.abc import Mapping
from typing import Any

from django.conf import settings

DEFAULTS: dict[str, Any] = {
    "LLM_BACKEND": "dummy",
    "LLM_MODEL": None,
    "MAX_ROWS": 500,
    "MAX_JOINS": 2,
    "MAX_METRICS": 5,
    "MAX_GROUP_BY": 3,
    "ALLOW_RAW_SQL": False,
    "SEND_SAMPLE_ROWS_TO_LLM": False,
    "DEFAULT_VISUALIZATION": "table",
    "API_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DUMMY_PLANS": {},
    "DUMMY_DEFAULT_PLAN": None,
}


def get_asklens_settings() -> dict[str, Any]:
    """Return AskLens settings merged with project overrides."""

    configured = getattr(settings, "DJANGO_ASKLENS", {})
    if not isinstance(configured, Mapping):
        msg = "DJANGO_ASKLENS must be a mapping."
        raise TypeError(msg)

    return {**DEFAULTS, **configured}


def get_asklens_setting(name: str) -> Any:
    """Return one AskLens setting by name."""

    return get_asklens_settings()[name]
