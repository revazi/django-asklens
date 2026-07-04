"""Django application configuration for Django AskLens."""

from django.apps import AppConfig


class AskLensConfig(AppConfig):
    """Application configuration for the reusable AskLens app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "django_asklens"
    label = "asklens"
    verbose_name = "Django AskLens"
