"""Admin registrations for Django AskLens."""

from django.contrib import admin

from django_asklens.models import SemanticQueryRun


@admin.register(SemanticQueryRun)
class SemanticQueryRunAdmin(admin.ModelAdmin):
    """Read-oriented admin for AskLens query-run audit records."""

    list_display = ("id", "user", "status", "row_count", "duration_ms", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("question", "error")
    readonly_fields = (
        "user",
        "question",
        "plan",
        "status",
        "row_count",
        "duration_ms",
        "error",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:
        """Prevent manual creation of audit records in admin."""

        return False
