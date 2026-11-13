from django.conf import settings
from django.db import models


class Order(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    total_cents = models.PositiveIntegerField()
