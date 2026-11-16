"""Opt-in session API and minimal table UI; requires only the api extra."""

from .web_settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "rest_framework"]  # noqa: F405
ROOT_URLCONF = "quickstart.api_urls"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}
