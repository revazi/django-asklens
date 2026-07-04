"""Minimal Django settings used by the test suite."""

SECRET_KEY = "django-asklens-test-secret-key"
DEBUG = True
USE_TZ = True
ROOT_URLCONF = "tests.test_project.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "django_asklens",
    "tests.test_project",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

MIDDLEWARE = []
MIGRATION_MODULES = {"test_project": None}

DJANGO_ASKLENS = {
    "MAX_ROWS": 50,
}
