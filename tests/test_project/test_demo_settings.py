"""Tests for runnable demo settings helpers."""

from tests.test_project import demo_settings
from tests.test_project.demo_settings import build_demo_asklens_settings


def test_demo_logging_routes_asklens_logs_to_console() -> None:
    """The runnable demo should show AskLens provider logs in the terminal."""

    assert demo_settings.LOGGING["loggers"]["django_asklens"]["level"] == "INFO"
    assert demo_settings.LOGGING["loggers"]["django_asklens"]["handlers"] == ["console"]


def test_demo_env_flag_requires_explicit_one() -> None:
    """Demo boolean env helpers only treat string 1 as enabled."""

    assert demo_settings.env_flag({}, "FEATURE") is False
    assert demo_settings.env_flag({"FEATURE": "0"}, "FEATURE") is False
    assert demo_settings.env_flag({"FEATURE": "true"}, "FEATURE") is False
    assert demo_settings.env_flag({"FEATURE": "1"}, "FEATURE") is True


def test_demo_asklens_settings_default_to_dummy_backend() -> None:
    """The runnable demo must not call live providers by default."""

    settings = build_demo_asklens_settings(environ={})

    assert settings["LLM_BACKEND"] == "dummy"
    assert settings["DUMMY_PLANS"]
    assert settings["MCP_ALLOW_ROW_RETURN"] is False
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
            "DJANGO_ASKLENS_LIVE_LLM_LOG_IO": "1",
        }
    )

    assert settings["LLM_BACKEND"] == "openai_compatible"
    assert settings["LLM_BASE_URL"] == "https://llm.example/v1"
    assert settings["LLM_API_KEY"] == "secret-test-key"
    assert settings["LLM_MODEL"] == "test-model"
    assert settings["LLM_TIMEOUT_SECONDS"] == 12
    assert settings["LLM_TEMPERATURE"] == 0.2
    assert settings["LOG_LLM_IO"] is True
    assert settings["DUMMY_PLANS"]


def test_demo_mcp_endpoint_flag_supports_primary_and_legacy_env_names() -> None:
    """The runnable demo mounts MCP only when an explicit env flag is set."""

    assert demo_settings.is_demo_mcp_enabled({}) is False
    assert demo_settings.is_demo_mcp_enabled({"DJANGO_ASKLENS_MCP_ENABLED": "1"})
    assert demo_settings.is_demo_mcp_enabled({"DJANGO_ASKLENS_DEMO_MCP": "1"})


def test_demo_asklens_settings_can_enable_mcp_row_return() -> None:
    """MCP row return remains an explicit opt-in demo setting."""

    settings = build_demo_asklens_settings(
        environ={"DJANGO_ASKLENS_MCP_ALLOW_ROWS": "1"}
    )

    assert settings["MCP_ALLOW_ROW_RETURN"] is True


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
