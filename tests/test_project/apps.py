"""Test-project application config placeholder."""

from django.apps import AppConfig


class TestProjectConfig(AppConfig):
    """Application config used only by tests."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tests.test_project"
