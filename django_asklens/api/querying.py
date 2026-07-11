"""Shared AskLens query orchestration for API and admin surfaces."""

from dataclasses import dataclass
from typing import Any, Literal

from django.core.exceptions import PermissionDenied

from django_asklens.api.permissions import get_request_permissions
from django_asklens.catalog.capabilities import build_capabilities
from django_asklens.exceptions import (
    AskLensError,
    LLMProviderError,
    PlanValidationError,
)
from django_asklens.execution import run_query_plan
from django_asklens.models import SemanticQueryRun
from django_asklens.planning import plan_asklens_response, plan_question
from django_asklens.planning.help import (
    QueryHelp,
    build_deterministic_query_help,
    build_query_help,
)
from django_asklens.planning.intents import (
    QuestionIntent,
    capabilities_intent,
    filter_capabilities_for_intent,
    is_capabilities_fallback_question,
    route_question_intent,
)
from django_asklens.planning.validation import parse_and_validate_query_plan
from django_asklens.settings import get_asklens_setting

QueryResponseType = Literal["query", "capabilities", "error"]


@dataclass(frozen=True, slots=True)
class AskLensQueryResponse:
    """A shared AskLens query/help response."""

    response_type: QueryResponseType
    payload: dict[str, Any]
    status_code: int = 200
    run: SemanticQueryRun | None = None


def execute_asklens_query_request(
    request: Any,
    *,
    question: str,
    debug: bool = False,
    include_visualization: bool = True,
    provided_plan: dict[str, Any] | None = None,
) -> AskLensQueryResponse:
    """Plan, execute, help, and audit one AskLens request.

    This is intentionally shared by the DRF API and Django admin query page so
    capability/help questions, live unified provider behavior, provided plans,
    audit writes, and safe fallbacks do not drift across surfaces.
    """

    enforce_debug_permission(request, debug=debug)
    permissions = get_request_permissions(request)

    try:
        if provided_plan is not None:
            plan = parse_and_validate_query_plan(
                provided_plan,
                permissions=permissions,
            )
        elif should_use_unified_provider_response():
            capabilities = build_capabilities(permissions=permissions)
            provider_result = plan_asklens_response(
                question,
                capabilities=capabilities,
                permissions=permissions,
            )
            if provider_result.response_type == "capabilities":
                assert provider_result.query_help is not None
                return AskLensQueryResponse(
                    response_type="capabilities",
                    payload=build_capabilities_payload(
                        question,
                        intent=capabilities_intent(),
                        source="semantic_provider",
                        capabilities=capabilities,
                        query_help=provider_result.query_help,
                        query_help_source="semantic_provider",
                    ),
                )
            assert provider_result.query_plan is not None
            plan = provider_result.query_plan
        else:
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
                return AskLensQueryResponse(
                    response_type="capabilities",
                    payload=build_capabilities_payload(
                        question,
                        intent=routing_result.intent,
                        source=routing_result.source,
                        capabilities=capabilities,
                        query_help=query_help,
                        query_help_source=query_help_source,
                        query_help_error=query_help_error,
                    ),
                )

            planner_result = plan_question(question, permissions=permissions)
            plan = planner_result.plan

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
        return AskLensQueryResponse(response_type="query", payload=payload, run=run)
    except AskLensError as exc:
        if should_return_capabilities_fallback(
            question,
            provided_plan=provided_plan,
        ):
            capabilities = build_capabilities(permissions=permissions)
            return AskLensQueryResponse(
                response_type="capabilities",
                payload=build_capabilities_payload(
                    question,
                    intent=capabilities_intent(confidence=0.5),
                    source="fallback",
                    capabilities=capabilities,
                    query_help=build_deterministic_query_help(
                        capabilities=capabilities,
                        question=question,
                        permissions=tuple(permissions),
                    ),
                    query_help_source="deterministic_fallback",
                    query_help_error=safe_provider_fallback_message(exc),
                ),
            )

        run = create_query_run(
            request=request,
            question=question,
            plan={},
            status=SemanticQueryRun.Status.FAILED,
            row_count=0,
            duration_ms=None,
            error=safe_error_message(exc),
        )
        return AskLensQueryResponse(
            response_type="error",
            status_code=400,
            run=run,
            payload={
                "run_id": run.pk,
                "question": question,
                "status": SemanticQueryRun.Status.FAILED,
                "error": safe_error_message(exc),
            },
        )


def should_use_unified_provider_response() -> bool:
    """Return whether live query requests should use one unified provider call."""

    return get_asklens_setting("LLM_BACKEND") != "dummy"


def should_return_capabilities_fallback(
    question: str,
    *,
    provided_plan: Any,
) -> bool:
    """Return whether a failed unified call should become deterministic help."""

    return (
        provided_plan is None
        and should_use_unified_provider_response()
        and is_capabilities_fallback_question(question)
    )


def enforce_debug_permission(request: Any, *, debug: bool) -> None:
    """Restrict debug mode to staff users."""

    if debug and not getattr(request.user, "is_staff", False):
        raise PermissionDenied("Debug mode is restricted to staff users.")


def get_user_permissions(request: Any) -> frozenset[str]:
    """Return permission strings for the authenticated request."""

    return get_request_permissions(request)


def create_query_run(
    *,
    request: Any,
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
                permissions=tuple(permissions or ()),
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
                permissions=tuple(permissions or ()),
            ),
            "deterministic_fallback",
            safe_provider_fallback_message(exc),
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
        "response_type": "query",
        "plan": plan,
        "columns": query_result["columns"],
        "data": query_result["data"],
        "row_count": query_result["row_count"],
        "duration_ms": query_result["duration_ms"],
        "result_metadata": build_result_metadata(
            plan=plan,
            row_count=query_result["row_count"],
        ),
        "explanation": "Executed a validated read-only AskLens query plan.",
    }
    if "visualization" in query_result:
        payload["visualization"] = query_result["visualization"]
    if debug:
        payload["debug"] = {"validated_plan": plan}
    return payload


def build_result_metadata(*, plan: dict[str, Any], row_count: int) -> dict[str, Any]:
    """Return alpha-safe metadata for result limits and possible truncation."""

    limit = int(plan.get("limit") or row_count or 0)
    limit_scope = "groups" if plan.get("intent") == "aggregate" else "rows"
    limit_reached = limit > 0 and row_count >= limit
    metadata: dict[str, Any] = {
        "limit": limit,
        "limit_scope": limit_scope,
        "limit_reached": limit_reached,
    }
    if limit_reached:
        max_rows = int(get_asklens_setting("MAX_ROWS"))
        metadata["limit_warning"] = (
            f"Returned {row_count} {limit_scope}, which reached the validated "
            f"plan limit of {limit}. There may be more matching {limit_scope}; "
            "refine filters, add ordering, or increase limit up to the "
            f"configured maximum of {max_rows}."
        )
    return metadata


def safe_provider_fallback_message(exc: AskLensError) -> str:
    """Return a provider-fallback reason without raw provider details."""

    category = safe_error_category(exc)
    if category == "provider_error":
        reason = "Provider request failed."
    elif category == "provider_validation_error":
        reason = "Provider output failed AskLens validation."
    else:
        reason = "Provider output could not be used."
    return f"{reason} Returned deterministic AskLens help instead."


def safe_error_category(exc: AskLensError) -> str:
    """Return a stable safe error category for diagnostics."""

    if isinstance(exc, LLMProviderError):
        return "provider_error"
    if isinstance(exc, PlanValidationError):
        return "provider_validation_error"
    return "asklens_error"


def safe_error_message(exc: AskLensError) -> str:
    """Return a safe API/audit error message without traceback details."""

    message = str(exc) or exc.__class__.__name__
    return " ".join(message.split())[:500]
