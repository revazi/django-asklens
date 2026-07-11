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
from django_asklens.planning.help import (
    QueryHelp,
    build_deterministic_query_help,
    build_query_help,
)
from django_asklens.planning.intents import (
    QuestionIntent,
    filter_capabilities_for_intent,
    route_question_intent,
)
from django_asklens.planning.validation import parse_and_validate_query_plan
from django_asklens.settings import get_asklens_setting


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
        provided_plan = serializer.validated_data.get("plan")
        enforce_debug_permission(request, debug=debug)
        permissions = get_request_permissions(request)

        try:
            routing_result = route_question_intent(question, permissions=permissions)
            if routing_result.intent.intent == "capabilities":
                capabilities = filter_capabilities_for_intent(
                    build_capabilities(permissions=permissions),
                    routing_result.intent,
                )
                (
                    query_help,
                    query_help_source,
                    query_help_error,
                ) = get_query_help_for_capabilities(
                    question,
                    capabilities=capabilities,
                    permissions=permissions,
                )
                return Response(
                    build_capabilities_payload(
                        question,
                        intent=routing_result.intent,
                        source=routing_result.source,
                        capabilities=capabilities,
                        query_help=query_help,
                        query_help_source=query_help_source,
                        query_help_error=query_help_error,
                    )
                )

            if provided_plan is None:
                planner_result = plan_question(
                    question,
                    permissions=permissions,
                )
                plan = planner_result.plan
            else:
                plan = parse_and_validate_query_plan(
                    provided_plan,
                    permissions=permissions,
                )
            query_result = run_query_plan(plan, request=request)
            run = create_query_run(
                request=request,
                question=question,
                plan=plan.model_dump(mode="json"),
                status=SemanticQueryRun.Status.SUCCESS,
                row_count=query_result.row_count,
                duration_ms=query_result.duration_ms,
            )
            payload = build_success_payload(
                run=run,
                question=question,
                plan=plan.model_dump(mode="json"),
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


def get_query_help_for_capabilities(
    question: str,
    *,
    capabilities: dict[str, Any],
    permissions: frozenset[str] | None = None,
) -> tuple[QueryHelp, str, str]:
    """Return LLM-backed query help when live mode is enabled."""

    if get_asklens_setting("LLM_BACKEND") == "dummy":
        return (
            build_deterministic_query_help(
                capabilities=capabilities,
                question=question,
            ),
            "deterministic",
            "",
        )
    try:
        return (
            build_query_help(
                question,
                capabilities=capabilities,
                permissions=tuple(permissions or ()),
            ),
            "semantic_provider",
            "",
        )
    except AskLensError as exc:
        return (
            build_deterministic_query_help(
                capabilities=capabilities,
                question=question,
            ),
            "deterministic_fallback",
            safe_error_message(exc),
        )


def build_capabilities_payload(
    question: str,
    *,
    intent: QuestionIntent,
    source: str,
    capabilities: dict[str, Any],
    query_help: QueryHelp,
    query_help_source: str,
    query_help_error: str = "",
) -> dict[str, Any]:
    """Build a natural-language help response without executing a query."""

    payload = {
        "question": question,
        "response_type": "capabilities",
        "capability_intent": intent.model_dump(mode="json"),
        "routing_source": source,
        "capabilities": capabilities,
        "query_help_source": query_help_source,
        "query_help": query_help.model_dump(mode="json"),
        "explanation": (
            "Returned permission-scoped AskLens capabilities and query-writing "
            "help without executing a database query."
        ),
    }
    if query_help_error:
        payload["query_help_error"] = query_help_error
    return payload


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
