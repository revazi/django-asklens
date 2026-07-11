"""Runnable local settings for the AskLens complex test project demo."""

import os
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

DUMMY_PLANS = {
    "Show paid billing revenue by product": {
        "resource": "billing_lines",
        "intent": "aggregate",
        "filters": [{"field": "billing_document.status", "op": "eq", "value": "PAID"}],
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
    "List facilities, facility name titles and facility owner full name as a table.": {
        "resource": "facility_staff_assignments",
        "intent": "list",
        "filters": [
            {"field": "role", "op": "eq", "value": "owner"},
            {"field": "is_active", "op": "eq", "value": True},
        ],
        "select": ["facility.name", "user.first_name", "user.last_name"],
        "order_by": [{"field": "facility.name", "direction": "asc"}],
        "limit": 20,
        "visualization": {"type": "table"},
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
    "Show campaign spend and conversions by channel": {
        "resource": "marketing_campaigns",
        "intent": "aggregate",
        "group_by": [{"field": "channel"}],
        "metrics": [
            {"name": "marketing_spend", "op": "sum", "field": "spend_cents"},
            {"name": "total_conversions", "op": "sum", "field": "conversions"},
        ],
        "order_by": [{"metric": "marketing_spend", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "channel", "y": "marketing_spend"},
    },
    "Count leads by source and stage": {
        "resource": "leads",
        "intent": "aggregate",
        "group_by": [{"field": "source"}, {"field": "stage"}],
        "metrics": [{"name": "lead_count", "op": "count", "field": "status"}],
        "order_by": [{"metric": "lead_count", "direction": "desc"}],
        "limit": 20,
        "visualization": {"type": "bar", "x": "source", "y": "lead_count"},
    },
    "Show booking attendance by session type": {
        "resource": "session_bookings",
        "intent": "aggregate",
        "group_by": [{"field": "session.session_type.name"}, {"field": "status"}],
        "metrics": [
            {"name": "booking_count", "op": "count", "field": "status"},
            {"name": "total_party_size", "op": "sum", "field": "party_size"},
        ],
        "order_by": [{"metric": "booking_count", "direction": "desc"}],
        "limit": 20,
        "visualization": {
            "type": "bar",
            "x": "session.session_type.name",
            "y": "booking_count",
        },
    },
    "Show staff labor minutes by role": {
        "resource": "staff_shifts",
        "intent": "aggregate",
        "group_by": [{"field": "role"}],
        "metrics": [
            {"name": "shift_count", "op": "count", "field": "status"},
            {"name": "actual_minutes", "op": "sum", "field": "actual_minutes"},
        ],
        "order_by": [{"metric": "actual_minutes", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "role", "y": "actual_minutes"},
    },
    "Show support tickets by priority and status": {
        "resource": "support_tickets",
        "intent": "aggregate",
        "group_by": [{"field": "priority"}, {"field": "status"}],
        "metrics": [{"name": "ticket_count", "op": "count", "field": "status"}],
        "order_by": [{"metric": "ticket_count", "direction": "desc"}],
        "limit": 20,
        "visualization": {"type": "bar", "x": "priority", "y": "ticket_count"},
    },
}


def build_demo_asklens_settings(environ=os.environ) -> dict:
    """Return AskLens settings for local demo mode.

    Dummy mode is the default and makes no network calls. Set
    DJANGO_ASKLENS_DEMO_LIVE_LLM=1 to use the OpenAI-compatible provider with
    credentials from environment variables.
    """

    asklens_settings = {
        "LLM_BACKEND": "dummy",
        "MAX_ROWS": 100,
        "MAX_JOINS": 2,
        "MAX_METRICS": 5,
        "MAX_GROUP_BY": 3,
        "API_PERMISSION_CLASSES": [
            "tests.test_project.permissions.CanUseComplexAnalytics"
        ],
        "REQUEST_PERMISSIONS_GETTER": (
            "tests.test_project.permissions.get_request_permissions"
        ),
        "DUMMY_PLANS": DUMMY_PLANS,
    }
    if environ.get("DJANGO_ASKLENS_DEMO_LIVE_LLM") != "1":
        return asklens_settings

    asklens_settings.update(
        {
            "LLM_BACKEND": "openai_compatible",
            "LLM_BASE_URL": environ.get(
                "DJANGO_ASKLENS_LIVE_LLM_BASE_URL",
                "https://api.openai.com/v1",
            ),
            "LLM_API_KEY": environ.get("DJANGO_ASKLENS_LIVE_LLM_API_KEY")
            or environ.get("OPENAI_API_KEY"),
            "LLM_MODEL": environ.get("DJANGO_ASKLENS_LIVE_LLM_MODEL"),
            "LLM_TIMEOUT_SECONDS": float(
                environ.get("DJANGO_ASKLENS_LIVE_LLM_TIMEOUT_SECONDS", "45")
            ),
            "LLM_TEMPERATURE": float(
                environ.get("DJANGO_ASKLENS_LIVE_LLM_TEMPERATURE", "0")
            ),
        }
    )
    return asklens_settings


DJANGO_ASKLENS = build_demo_asklens_settings()
