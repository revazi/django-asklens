from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"

    def ready(self):
        # One startup import; do not also import registration from models or URLs.
        from . import asklens_registration  # noqa: F401
