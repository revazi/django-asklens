"""Models used by Django AskLens tests."""

from django.conf import settings
from django.db import models


class Account(models.Model):
    """Tenant/account fixture model for API security tests."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        app_label = "test_project"


class AccountMembership(models.Model):
    """User-to-account membership fixture model for tenant scoping tests."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    role = models.CharField(max_length=32, default="member")

    class Meta:
        app_label = "test_project"
        unique_together = ("user", "account")


class Customer(models.Model):
    """Customer fixture model for catalog tests."""

    name = models.CharField(max_length=100)
    email = models.EmailField()

    class Meta:
        app_label = "test_project"


class Order(models.Model):
    """Order fixture model for catalog tests."""

    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    internal_notes = models.TextField(blank=True)

    class Meta:
        app_label = "test_project"
