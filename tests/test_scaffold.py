"""Smoke tests for the minimal Django AskLens scaffold."""

from django.apps import apps

import django_asklens
from django_asklens.apps import AskLensConfig
from django_asklens.settings import DEFAULTS, get_asklens_settings


def test_package_imports() -> None:
    assert django_asklens.__version__ == "0.3.1"


def test_app_config_metadata() -> None:
    assert AskLensConfig.name == "django_asklens"
    assert AskLensConfig.label == "asklens"
    assert AskLensConfig.verbose_name == "Django AskLens"


def test_django_app_is_installed() -> None:
    app_config = apps.get_app_config("asklens")

    assert isinstance(app_config, AskLensConfig)
    assert app_config.name == "django_asklens"


def test_settings_merge_project_overrides() -> None:
    asklens_settings = get_asklens_settings()

    assert asklens_settings["MAX_ROWS"] == 50
    assert asklens_settings["LLM_BACKEND"] == "dummy"


def test_default_settings_are_not_mutated() -> None:
    assert DEFAULTS["MAX_ROWS"] == 500
    assert DEFAULTS["AUDIT_INCLUDE_CONTENT"] is False
