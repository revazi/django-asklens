"""Runnable local settings for the AskLens complex test project demo."""

from pathlib import Path

from tests.test_project.settings import *  # noqa: F403

BASE_DIR = Path(__file__).resolve().parents[2]

ROOT_URLCONF = "tests.test_project.demo_urls"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
STATIC_URL = "static/"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_asklens",
    "tests.test_project.apps.TestProjectConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / ".asklens-test-project.sqlite3",
    },
}

MIGRATION_MODULES = {"test_project": None}
TEST_PROJECT_REGISTER_COMPLEX_ASKLENS = True

DJANGO_ASKLENS = {
    "MAX_ROWS": 100,
    "MAX_JOINS": 2,
    "MAX_METRICS": 5,
    "MAX_GROUP_BY": 3,
    "API_PERMISSION_CLASSES": ["tests.test_project.permissions.CanUseComplexAnalytics"],
    "REQUEST_PERMISSIONS_GETTER": (
        "tests.test_project.permissions.get_request_permissions"
    ),
}
