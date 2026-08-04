"""Strict synthetic PostgreSQL settings for database-sensitive tests."""

import os

from django.core.exceptions import ImproperlyConfigured

from tests.test_project.settings import *  # noqa: F403


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"{name} is required for PostgreSQL tests")
    return value


POSTGRES_EXPECTED_MAJOR = _required_environment(
    "DJANGO_ASKLENS_POSTGRES_EXPECTED_MAJOR"
)
if POSTGRES_EXPECTED_MAJOR not in {"15", "18"}:
    raise ImproperlyConfigured(
        "DJANGO_ASKLENS_POSTGRES_EXPECTED_MAJOR must be 15 or 18"
    )

try:
    POSTGRES_PORT = int(_required_environment("DJANGO_ASKLENS_POSTGRES_PORT"))
except ValueError as exc:
    raise ImproperlyConfigured(
        "DJANGO_ASKLENS_POSTGRES_PORT must be an integer"
    ) from exc

MIGRATION_MODULES = {
    "auth": None,
    "contenttypes": None,
    "test_project": None,
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _required_environment("DJANGO_ASKLENS_POSTGRES_DB"),
        "USER": _required_environment("DJANGO_ASKLENS_POSTGRES_USER"),
        "PASSWORD": _required_environment("DJANGO_ASKLENS_POSTGRES_PASSWORD"),
        "HOST": _required_environment("DJANGO_ASKLENS_POSTGRES_HOST"),
        "PORT": POSTGRES_PORT,
        "CONN_MAX_AGE": 0,
    }
}
