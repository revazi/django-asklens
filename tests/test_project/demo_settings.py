"""Runnable local settings for the AskLens complex test project demo."""

from pathlib import Path

from tests.test_project.settings import *  # noqa: F403

BASE_DIR = Path(__file__).resolve().parents[2]

ROOT_URLCONF = "tests.test_project.demo_urls"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]", "testserver"]
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
    "LLM_BACKEND": "dummy",
    "MAX_ROWS": 100,
    "MAX_JOINS": 2,
    "MAX_METRICS": 5,
    "MAX_GROUP_BY": 3,
    "API_PERMISSION_CLASSES": ["tests.test_project.permissions.CanUseComplexAnalytics"],
    "REQUEST_PERMISSIONS_GETTER": (
        "tests.test_project.permissions.get_request_permissions"
    ),
    "DUMMY_PLANS": {
        "Show paid billing revenue by product": {
            "resource": "billing_lines",
            "intent": "aggregate",
            "filters": [
                {"field": "billing_document.status", "op": "eq", "value": "PAID"}
            ],
            "group_by": [{"field": "product_name"}],
            "metrics": [
                {
                    "name": "gross_revenue",
                    "op": "sum",
                    "field": "total_amount_cents",
                }
            ],
            "order_by": [{"metric": "gross_revenue", "direction": "desc"}],
            "limit": 10,
            "visualization": {
                "type": "bar",
                "x": "product_name",
                "y": "gross_revenue",
            },
        },
        "Show payment totals by status": {
            "resource": "payment_attempts",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [
                {"name": "payment_count", "op": "count", "field": "status"},
                {"name": "payment_amount", "op": "sum", "field": "amount_cents"},
            ],
            "order_by": [{"metric": "payment_amount", "direction": "desc"}],
            "limit": 10,
            "visualization": {
                "type": "bar",
                "x": "status",
                "y": "payment_amount",
            },
        },
        "List member contact emails": {
            "resource": "member_contacts",
            "intent": "list",
            "select": ["facility.name", "first_name", "last_name", "email"],
            "order_by": [{"field": "email", "direction": "asc"}],
            "limit": 20,
            "visualization": {"type": "table"},
        },
        "Count member subscriptions by plan and status": {
            "resource": "member_subscriptions",
            "intent": "aggregate",
            "group_by": [{"field": "plan.name"}, {"field": "status"}],
            "metrics": [
                {
                    "name": "subscription_count",
                    "op": "count",
                    "field": "status",
                }
            ],
            "order_by": [{"metric": "subscription_count", "direction": "desc"}],
            "limit": 20,
            "visualization": {
                "type": "bar",
                "x": "plan.name",
                "y": "subscription_count",
            },
        },
        "Show scheduled capacity by session type": {
            "resource": "schedule_sessions",
            "intent": "aggregate",
            "group_by": [{"field": "session_type.name"}],
            "metrics": [
                {"name": "session_count", "op": "count", "field": "start_date"},
                {"name": "total_capacity", "op": "sum", "field": "capacity"},
                {
                    "name": "average_duration",
                    "op": "avg",
                    "field": "duration_minutes",
                },
            ],
            "order_by": [{"metric": "total_capacity", "direction": "desc"}],
            "limit": 10,
            "visualization": {
                "type": "bar",
                "x": "session_type.name",
                "y": "total_capacity",
            },
        },
    },
}
