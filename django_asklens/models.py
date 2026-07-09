"""Database models owned by Django AskLens."""

from django.conf import settings
from django.db import models


class SemanticQueryRun(models.Model):
    """Audit record for one AskLens query attempt."""

    class Status(models.TextChoices):
        """Supported query-run statuses."""

        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asklens_query_runs",
    )
    question = models.TextField()
    plan = models.JSONField(default=dict)
    status = models.CharField(max_length=32, choices=Status.choices)
    row_count = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        """Return a compact admin/debug representation."""

        return f"AskLens run {self.pk or 'unsaved'}: {self.status}"


class AskLensQuery(SemanticQueryRun):
    """Admin-only proxy used as a dedicated AskLens query page."""

    class Meta:
        proxy = True
        verbose_name = "AskLens query"
        verbose_name_plural = "AskLens queries"
        default_permissions = ()
