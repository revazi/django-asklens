"""Local-only SQLite settings; do not use this project as a deployment template."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "synthetic-asklens-consumer-not-for-deployment"
DEBUG = False
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django_asklens",
    "shop.apps.ShopConfig",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"


def order_plan(status):
    """Reviewed fixture plans, never caller-supplied authorization or SQL."""
    return {
        "query_plan": {
            "resource": "orders",
            "intent": "list",
            "select": ["product", "total_cents"],
            "filters": [{"field": "status", "op": "eq", "value": status}],
            "limit": 10,
        }
    }


DJANGO_ASKLENS = {
    "LLM_BACKEND": "dummy",
    "DUMMY_PLANS": {
        "Show my paid orders": order_plan("paid"),
        "Show my refunded orders": order_plan("refunded"),
    },
    "DUMMY_DEFAULT_PLAN": None,
    "AUDIT_MODE": "database",
    "AUDIT_INCLUDE_CONTENT": False,
}
