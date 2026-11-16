"""Opt-in Django-only admin; synthetic local settings, not a deployment template."""

from .settings import *  # noqa: F403

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
INSTALLED_APPS = [  # noqa: F405
    *INSTALLED_APPS,  # noqa: F405
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.contrib.staticfiles",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
ROOT_URLCONF = "quickstart.web_urls"
STATIC_URL = "/static/"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/table/"
DJANGO_ASKLENS = {  # noqa: F405
    **DJANGO_ASKLENS,  # noqa: F405
    "API_PERMISSION_CLASSES": ["django_asklens.access.IsAuthenticated"],
    "REQUEST_PERMISSIONS_GETTER": None,
}
