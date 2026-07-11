"""Optional packaged frontend for querying AskLens from a browser."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.module_loading import import_string

from django_asklens.settings import get_asklens_setting

FrontendPermissionCheck = Callable[[HttpRequest], bool]


def asklens_frontend(request: HttpRequest) -> HttpResponse:
    """Render the optional packaged AskLens query frontend."""

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return redirect_to_login(request.get_full_path())
    enforce_frontend_access(request)
    return render_asklens_frontend(request)


def render_asklens_frontend(
    request: HttpRequest,
    *,
    extra_context: Mapping[str, Any] | None = None,
) -> HttpResponse:
    """Render the packaged AskLens frontend with optional project context."""

    context = build_frontend_context(request)
    if extra_context:
        context.update(dict(extra_context))
    return render(request, "django_asklens/frontend/query.html", context)


def build_frontend_context(request: HttpRequest) -> dict[str, Any]:
    """Return safe context for the packaged AskLens frontend."""

    return {
        "page_title": get_asklens_setting("FRONTEND_TITLE"),
        "page_subtitle": get_asklens_setting("FRONTEND_SUBTITLE"),
        "catalog_url": reverse("django_asklens:catalog"),
        "capabilities_url": reverse("django_asklens:capabilities"),
        "query_url": reverse("django_asklens:query"),
        "starter_questions": normalize_string_sequence(
            get_asklens_setting("FRONTEND_STARTER_QUESTIONS")
        ),
        "scope_labels": (),
        "scope_title": "Visible row scope",
        "llm_backend": get_asklens_setting("LLM_BACKEND"),
        "llm_mode_label": get_llm_mode_label(),
        "llm_model": get_asklens_setting("LLM_MODEL"),
        "user_label": get_user_label(request),
    }


def enforce_frontend_access(request: HttpRequest) -> None:
    """Require authentication and optional project-specific frontend permission."""

    permission_check = get_frontend_permission_check()
    if permission_check is not None and not permission_check(request):
        raise PermissionDenied("You do not have permission to use AskLens.")


def get_frontend_permission_check() -> FrontendPermissionCheck | None:
    """Return the configured project-specific frontend permission check."""

    configured = get_asklens_setting("FRONTEND_PERMISSION_CHECK")
    if configured is None:
        return None
    if isinstance(configured, str):
        configured = import_string(configured)
    if not callable(configured):
        msg = "DJANGO_ASKLENS['FRONTEND_PERMISSION_CHECK'] must be callable."
        raise TypeError(msg)
    return configured


def normalize_string_sequence(value: Any) -> tuple[str, ...]:
    """Normalize configured strings without accepting a bare string."""

    if value is None:
        return ()
    if isinstance(value, str):
        msg = "AskLens frontend string sequences must be lists or tuples, not strings."
        raise TypeError(msg)
    if not isinstance(value, Sequence):
        msg = "AskLens frontend string sequences must be lists or tuples."
        raise TypeError(msg)
    return tuple(str(item) for item in value if str(item).strip())


def get_llm_mode_label() -> str:
    """Return a safe human-readable planner/LLM status label."""

    backend = get_asklens_setting("LLM_BACKEND")
    if backend == "dummy":
        return "Offline dummy plans"
    if backend == "openai_compatible":
        return "Live LLM enabled"
    return f"Custom backend: {backend}"


def get_user_label(request: HttpRequest) -> str:
    """Return a safe label for the current user."""

    user = getattr(request, "user", None)
    if user is None:
        return "Unknown user"
    label = getattr(user, "get_username", lambda: "")()
    return label or str(user)
