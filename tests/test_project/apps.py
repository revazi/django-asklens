"""Test-project application config."""

from django.apps import AppConfig


class TestProjectConfig(AppConfig):
    """Application config used by tests and the runnable local demo."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tests.test_project"

    def ready(self) -> None:
        """Optionally register complex AskLens resources for the demo server."""

        from django.conf import settings

        if not getattr(settings, "TEST_PROJECT_REGISTER_COMPLEX_ASKLENS", False):
            return

        from tests.test_project.asklens_registry import (
            ensure_complex_resources_registered,
        )

        ensure_complex_resources_registered()
