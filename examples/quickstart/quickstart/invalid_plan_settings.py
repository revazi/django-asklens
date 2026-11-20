"""Article-only offline failure fixture, never a deployment configuration."""

from .settings import *  # noqa: F403

DJANGO_ASKLENS = {
    **DJANGO_ASKLENS,  # noqa: F405
    "DUMMY_PLANS": {
        "Show my paid orders": {
            "query_plan": {
                "resource": "orders",
                "intent": "list",
                "select": ["product", "total_cents"],
                "limit": "ten",
            }
        }
    },
}
