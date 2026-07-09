"""Tests for runnable demo settings helpers."""

from tests.test_project.demo_settings import build_demo_asklens_settings


def test_demo_asklens_settings_default_to_dummy_backend() -> None:
    """The runnable demo must not call live providers by default."""

    settings = build_demo_asklens_settings(environ={})

    assert settings["LLM_BACKEND"] == "dummy"
    assert settings["DUMMY_PLANS"]
    assert "LLM_API_KEY" not in settings


def test_demo_asklens_settings_can_enable_openai_compatible_backend() -> None:
    """Environment variables can opt the demo into live LLM mode."""

    settings = build_demo_asklens_settings(
        environ={
            "DJANGO_ASKLENS_DEMO_LIVE_LLM": "1",
            "DJANGO_ASKLENS_LIVE_LLM_BASE_URL": "https://llm.example/v1",
            "DJANGO_ASKLENS_LIVE_LLM_API_KEY": "secret-test-key",
            "DJANGO_ASKLENS_LIVE_LLM_MODEL": "test-model",
            "DJANGO_ASKLENS_LIVE_LLM_TIMEOUT_SECONDS": "12",
            "DJANGO_ASKLENS_LIVE_LLM_TEMPERATURE": "0.2",
        }
    )

    assert settings["LLM_BACKEND"] == "openai_compatible"
    assert settings["LLM_BASE_URL"] == "https://llm.example/v1"
    assert settings["LLM_API_KEY"] == "secret-test-key"
    assert settings["LLM_MODEL"] == "test-model"
    assert settings["LLM_TIMEOUT_SECONDS"] == 12
    assert settings["LLM_TEMPERATURE"] == 0.2
    assert settings["DUMMY_PLANS"]


def test_demo_asklens_settings_can_use_openai_api_key_fallback() -> None:
    """The demo can use OPENAI_API_KEY when the AskLens-specific key is absent."""

    settings = build_demo_asklens_settings(
        environ={
            "DJANGO_ASKLENS_DEMO_LIVE_LLM": "1",
            "DJANGO_ASKLENS_LIVE_LLM_MODEL": "test-model",
            "OPENAI_API_KEY": "fallback-secret-test-key",
        }
    )

    assert settings["LLM_API_KEY"] == "fallback-secret-test-key"
