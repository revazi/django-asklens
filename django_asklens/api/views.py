"""DRF views for the AskLens API."""

from typing import Any

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django_asklens.api.permissions import (
    get_api_permission_classes,
    get_request_permissions,
)
from django_asklens.api.serializers import (
    QueryRequestSerializer,
    SemanticQueryRunSerializer,
)
from django_asklens.catalog.capabilities import build_capabilities
from django_asklens.catalog.registry import serialize_catalog
from django_asklens.exceptions import AskLensError
from django_asklens.execution import run_query_plan
from django_asklens.models import SemanticQueryRun
from django_asklens.planning import plan_question


class AskLensAPIView(APIView):
    """Base API view with configurable AskLens permissions."""

    def get_permissions(self):
        """Instantiate configured permission classes."""

        return [permission() for permission in get_api_permission_classes()]


class CatalogView(AskLensAPIView):
    """Return safe semantic catalog metadata."""

    def get(self, request: Request) -> Response:
        """Return catalog metadata visible to the planner by default."""

        return Response(serialize_catalog(permissions=get_request_permissions(request)))


class CapabilitiesView(AskLensAPIView):
    """Return permission-scoped guidance about what can be queried."""

    def get(self, request: Request) -> Response:
        """Return safe capabilities derived from visible catalog metadata."""

        return Response(
            build_capabilities(permissions=get_request_permissions(request))
        )


class QueryView(AskLensAPIView):
    """Plan, execute, and audit one natural-language query."""

    def post(self, request: Request) -> Response:
        """Execute one AskLens query request."""

        serializer = QueryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["question"]
        debug = serializer.validated_data["debug"]
        include_visualization = serializer.validated_data["include_visualization"]
        enforce_debug_permission(request, debug=debug)

        try:
            planner_result = plan_question(
                question,
                permissions=get_request_permissions(request),
            )
            query_result = run_query_plan(planner_result.plan, request=request)
            run = create_query_run(
                request=request,
                question=question,
                plan=planner_result.plan.model_dump(mode="json"),
                status=SemanticQueryRun.Status.SUCCESS,
                row_count=query_result.row_count,
                duration_ms=query_result.duration_ms,
            )
            payload = build_success_payload(
                run=run,
                question=question,
                plan=planner_result.plan.model_dump(mode="json"),
                query_result=query_result.to_dict(
                    include_visualization=include_visualization,
                ),
                debug=debug,
            )
            return Response(payload)
        except AskLensError as exc:
            run = create_query_run(
                request=request,
                question=question,
                plan={},
                status=SemanticQueryRun.Status.FAILED,
                row_count=0,
                duration_ms=None,
                error=safe_error_message(exc),
            )
            return Response(
                {
                    "run_id": run.pk,
                    "question": question,
                    "status": SemanticQueryRun.Status.FAILED,
                    "error": safe_error_message(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class QueryRunDetailView(AskLensAPIView):
    """Return one audited query run."""

    def get(self, request: Request, pk: int) -> Response:
        """Return a query run if the requester may view it."""

        run = get_object_or_404(SemanticQueryRun, pk=pk)
        if not can_view_run(request, run):
            raise PermissionDenied("You do not have access to this AskLens run.")
        return Response(SemanticQueryRunSerializer(run).data)


def enforce_debug_permission(request: Request, *, debug: bool) -> None:
    """Restrict debug mode to staff users."""

    if debug and not getattr(request.user, "is_staff", False):
        raise PermissionDenied("Debug mode is restricted to staff users.")


def get_user_permissions(request: Request) -> frozenset[str]:
    """Return permission strings for the authenticated request.

    Kept as a small compatibility alias for code importing the previous helper.
    """

    return get_request_permissions(request)


def create_query_run(
    *,
    request: Request,
    question: str,
    plan: dict[str, Any],
    status: str,
    row_count: int,
    duration_ms: int | None = None,
    error: str = "",
) -> SemanticQueryRun:
    """Persist one safe query-run audit record."""

    user = request.user if getattr(request.user, "is_authenticated", False) else None
    return SemanticQueryRun.objects.create(
        user=user,
        question=question,
        plan=plan,
        status=status,
        row_count=row_count,
        duration_ms=duration_ms,
        error=error,
    )


def build_success_payload(
    *,
    run: SemanticQueryRun,
    question: str,
    plan: dict[str, Any],
    query_result: dict[str, Any],
    debug: bool,
) -> dict[str, Any]:
    """Build a user-facing successful query response."""

    payload = {
        "run_id": run.pk,
        "question": question,
        "plan": plan,
        "columns": query_result["columns"],
        "data": query_result["data"],
        "row_count": query_result["row_count"],
        "duration_ms": query_result["duration_ms"],
        "explanation": "Executed a validated read-only AskLens query plan.",
    }
    if "visualization" in query_result:
        payload["visualization"] = query_result["visualization"]
    if debug:
        payload["debug"] = {"validated_plan": plan}
    return payload


def can_view_run(request: Request, run: SemanticQueryRun) -> bool:
    """Return whether a request user can view a run."""

    user = request.user
    if getattr(user, "is_staff", False):
        return True
    return bool(getattr(user, "is_authenticated", False) and run.user_id == user.pk)


def safe_error_message(exc: AskLensError) -> str:
    """Return a safe API/audit error message without traceback details."""

    return str(exc) or exc.__class__.__name__
