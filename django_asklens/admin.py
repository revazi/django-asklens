"""Admin registrations for Django AskLens."""

from typing import Any
from urllib.parse import urlencode

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import format_html

from django_asklens.admin_querying import build_admin_result, execute_admin_query
from django_asklens.api.permissions import get_api_permission_classes
from django_asklens.models import AskLensQuery, SemanticQueryRun


class AskLensAdminQueryForm(forms.Form):
    """Admin form for running one AskLens query."""

    question = forms.CharField(
        label="Question",
        widget=forms.Textarea(attrs={"rows": 3, "cols": 100}),
        help_text=(
            "Ask a data question or ask for examples. Admin uses the same "
            "planning and help flow as /asklens/query/."
        ),
    )


@admin.register(SemanticQueryRun)
class SemanticQueryRunAdmin(admin.ModelAdmin):
    """Read-oriented admin for AskLens query-run audit records."""

    list_display = (
        "id",
        "user",
        "status",
        "row_count",
        "duration_ms",
        "created_at",
        "query_result_link",
    )
    list_filter = ("status", "created_at")
    search_fields = ("question", "error")
    search_help_text = (
        "Search existing AskLens audit records. To run a question, use the "
        "separate AskLens queries admin page."
    )
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

    @admin.display(description="Question")
    def query_result_link(self, obj: SemanticQueryRun) -> str:
        """Return a link to open this question in the query admin."""

        url = admin_query_url(obj.question)
        return format_html('<a href="{}">Open question</a>', url)


@admin.register(AskLensQuery)
class AskLensQueryAdmin(admin.ModelAdmin):
    """Dedicated admin page for running AskLens queries and viewing rows."""

    def has_add_permission(self, request) -> bool:
        """Prevent manual creation for the proxy admin model."""

        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """Prevent editing through the proxy admin model."""

        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        """Prevent deleting through the proxy admin model."""

        return False

    def has_view_permission(self, request, obj=None) -> bool:
        """Allow staff users to open the query page.

        Actual query execution is still checked against AskLens API permission
        classes and request-derived field permissions.
        """

        return bool(getattr(request.user, "is_staff", False))

    def changelist_view(self, request, extra_context=None):
        """Render and process the dedicated AskLens admin query page."""

        if not self.has_view_permission(request):
            raise PermissionDenied("You do not have permission to query AskLens.")

        result: dict[str, Any] | None = None
        error = ""
        run: SemanticQueryRun | None = None
        initial = {"question": request.GET.get("question", "")}
        form = AskLensAdminQueryForm(request.POST or None, initial=initial)

        if request.method == "POST" and form.is_valid():
            if not can_query_asklens_from_admin(request):
                raise PermissionDenied("You do not have permission to query AskLens.")
            result, run, error, reused_existing_run = execute_admin_query(
                request,
                question=form.cleaned_data["question"],
            )
        else:
            reused_existing_run = False

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "AskLens query",
            "form": form,
            "result": build_admin_result(result) if result is not None else None,
            "error": error,
            "run": run,
            "reused_existing_run": reused_existing_run,
            "audit_changelist_url": reverse(
                "admin:asklens_semanticqueryrun_changelist"
            ),
        }
        if extra_context:
            context.update(extra_context)
        return render(
            request,
            "admin/django_asklens/asklensquery/change_list.html",
            context,
        )


def can_query_asklens_from_admin(request) -> bool:
    """Return whether configured AskLens API permissions allow this request."""

    return all(
        permission_class().has_permission(request, None)
        for permission_class in get_api_permission_classes()
    )


def admin_query_url(question: str = "") -> str:
    """Return the AskLens query admin URL, optionally prefilled."""

    url = reverse("admin:asklens_asklensquery_changelist")
    if not question:
        return url
    return f"{url}?{urlencode({'question': question})}"
