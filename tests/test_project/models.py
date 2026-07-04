"""Models used by Django AskLens tests."""

from django.db import models


class Customer(models.Model):
    """Customer fixture model for catalog tests."""

    name = models.CharField(max_length=100)
    email = models.EmailField()

    class Meta:
        app_label = "test_project"


class Order(models.Model):
    """Order fixture model for catalog tests."""

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    internal_notes = models.TextField(blank=True)

    class Meta:
        app_label = "test_project"
