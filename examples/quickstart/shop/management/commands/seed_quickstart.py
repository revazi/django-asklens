"""Seed only this disposable example; never run against a host application's DB."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from shop.models import Order


class Command(BaseCommand):
    help = "Create synthetic local users/orders; repeat without duplicating rows."

    @transaction.atomic
    def handle(self, *args, **options):
        permission = Permission.objects.get(
            content_type__app_label="shop",
            content_type__model="order",
            codename="view_order",
        )
        users = {}
        for name in ("alice", "bob", "no-report"):
            user, created = get_user_model().objects.get_or_create(
                username=f"asklens-{name}"
            )
            if not created:
                # Refuse to repurpose a real account or a changed demo role.
                if user.has_usable_password() or user.is_staff or user.is_superuser:
                    raise CommandError(
                        "Refusing to modify an existing privileged user."
                    )
            else:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            if name != "no-report":
                user.user_permissions.add(permission)
            users[name] = user

        for name, product, status, cents in (
            ("alice", "North class", "paid", 2000),
            ("alice", "North membership", "paid", 1200),
            ("alice", "North draft", "draft", 500),
            ("bob", "South membership", "paid", 9900),
        ):
            Order.objects.get_or_create(
                owner=users[name],
                product=product,
                defaults={"status": status, "total_cents": cents},
            )
        self.stdout.write("Synthetic users/orders ready; no login passwords were set.")
