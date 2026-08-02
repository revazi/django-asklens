"""Framework-neutral AskLens query/help orchestration."""

from dataclasses import dataclass
from typing import Any, Literal

from django.core.exceptions import PermissionDenied

from django_asklens.catalog.capabilities import (
    build_capabilities,
    build_query_guidance,
)
from django_asklens.catalog.registry import serialize_catalog
from django_asklens.exceptions import (
    AskLensError,
    PublicErrorPayload,
    public_error_payload,
)
from django_asklens.execution import QueryResult, execute_plan
from django_asklens.execution.audit import (
    _audit_external_rejection,
    _execution_audit_content,
)
from django_asklens.models import SemanticQueryRun
from django_asklens.permissions import get_request_permissions
from django_asklens.planning import (
    PresentationSpec,
    parse_presentation,
    plan_asklens_response,
    plan_question,
)
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
from django_asklens.results import normalize_presentation
from django_asklens.settings import get_asklens_setting

QueryResponseType = Literal["query", "capabilities", "error"]

__all__ = [
    "AskLensQueryResponse",
    "QueryResponseType",
    "build_capabilities_payload",
    "build_result_metadata",
    "build_success_payload",
    "enforce_debug_permission",
    "execute_asklens_query_request",
    "get_query_help_for_capabilities",
    "get_user_permissions",
    "safe_error_category",
    "safe_error_message",
    "safe_error_payload",
    "safe_provider_fallback_message",
    "should_return_capabilities_fallback",
    "should_use_unified_provider_response",
]


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
    include_presentation: bool = True,
    provided_plan: str | bytes | dict[str, Any] | None = None,
    provided_presentation: dict[str, Any] | None = None,
) -> AskLensQueryResponse:
    """Plan, execute, help, and audit one AskLens request.

    This is intentionally shared by the DRF API and Django admin query page so
    capability/help questions, live unified provider behavior, provided plans,
    audit writes, and safe fallbacks do not drift across surfaces.
    """

    enforce_debug_permission(request, debug=debug)
    permissions = get_request_permissions(request)

    try:
        with _execution_audit_content(question=question):
            presentation = parse_presentation(provided_presentation)
            if provided_plan is not None:
                untrusted_plan = provided_plan
            elif should_use_unified_provider_response():
                query_guidance = build_query_guidance(permissions=permissions)
                provider_result = plan_asklens_response(
                    question,
                    capabilities=query_guidance,
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
                            permissions=permissions,
                            query_help=provider_result.query_help,
                            query_help_source="semantic_provider",
                        ),
                    )
                assert provider_result.query_plan is not None
                untrusted_plan = provider_result.query_plan
                if presentation is None:
                    presentation = provider_result.presentation
            else:
                routing_result = route_question_intent(
                    question,
                    permissions=permissions,
                )
                if routing_result.intent.intent == "capabilities":
                    query_guidance = filter_capabilities_for_intent(
                        build_query_guidance(permissions=permissions),
                        routing_result.intent,
                    )
                    (
                        query_help,
                        query_help_source,
                        query_help_error,
                    ) = get_query_help_for_capabilities(
                        question,
                        capabilities=query_guidance,
                        permissions=permissions,
                    )
                    return AskLensQueryResponse(
                        response_type="capabilities",
                        payload=build_capabilities_payload(
                            question,
                            intent=routing_result.intent,
                            source=routing_result.source,
                            permissions=permissions,
                            query_help=query_help,
                            query_help_source=query_help_source,
                            query_help_error=query_help_error,
                        ),
                    )

                planner_result = plan_question(question, permissions=permissions)
                untrusted_plan = planner_result.plan
                if presentation is None:
                    presentation = planner_result.presentation

            query_result = execute_plan(untrusted_plan, request=request)
            plan = query_result._validated_plan
            assert plan is not None
            run = _database_audit_record(query_result._audit_record)
            payload = build_success_payload(
                run=run,
                question=question,
                plan=plan.model_dump(mode="json"),
                query_result=query_result.to_dict(),
                presentation=build_presentation_payload(
                    presentation,
                    query_result=query_result,
                    include_presentation=include_presentation,
                ),
                debug=debug,
            )
            return AskLensQueryResponse(
                response_type="query",
                payload=payload,
                run=run,
            )
    except AskLensError as exc:
        if should_return_capabilities_fallback(
            question,
            provided_plan=provided_plan,
        ):
            query_guidance = build_query_guidance(permissions=permissions)
            return AskLensQueryResponse(
                response_type="capabilities",
                payload=build_capabilities_payload(
                    question,
                    intent=capabilities_intent(confidence=0.5),
                    source="fallback",
                    permissions=permissions,
                    query_help=build_deterministic_query_help(
                        capabilities=query_guidance,
                        question=question,
                        permissions=tuple(permissions),
                    ),
                    query_help_source="deterministic_fallback",
                    query_help_error=safe_provider_fallback_message(exc),
                ),
            )

        run = _database_audit_record(getattr(exc, "_audit_record", None))
        if not getattr(exc, "_audit_attempted", False):
            with _execution_audit_content(question=question):
                run = _database_audit_record(
                    _audit_external_rejection(request=request, error=exc)
                )

        error_payload = safe_error_payload(exc)
        payload: dict[str, Any] = {
            "question": question,
            "status": SemanticQueryRun.Status.FAILED,
            "error": error_payload,
        }
        if run is not None:
            payload["run_id"] = run.pk
        return AskLensQueryResponse(
            response_type="error",
            status_code=400,
            run=run,
            payload=payload,
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


def _database_audit_record(value: Any) -> SemanticQueryRun | None:
    """Return a database audit record and ignore custom-sink return values."""

    return value if isinstance(value, SemanticQueryRun) else None


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
    permissions: frozenset[str],
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
        "capabilities": build_capabilities(),
        "catalog": serialize_catalog(permissions=permissions),
        "query_help_source": query_help_source,
        "query_help": query_help.model_dump(mode="json"),
        "explanation": (
            "Returned machine capabilities, permission-scoped catalog metadata, "
            "and query-writing help without executing a database query."
        ),
    }
    if query_help_error:
        payload["query_help_error"] = query_help_error
    return payload


def build_success_payload(
    *,
    run: SemanticQueryRun | None,
    question: str,
    plan: dict[str, Any],
    query_result: dict[str, Any],
    presentation: dict[str, Any] | None,
    debug: bool,
) -> dict[str, Any]:
    """Build a user-facing successful query response."""

    payload = {
        "question": question,
        "response_type": "query",
        "plan": plan,
        "columns": query_result["columns"],
        "data": query_result["data"],
        "row_count": query_result["row_count"],
        "duration_ms": query_result["duration_ms"],
        "result_metadata": build_result_metadata(
            limit=int(query_result["result_metadata"]["limit"]),
            limit_scope=query_result["result_metadata"]["limit_scope"],
            truncated=bool(query_result["result_metadata"]["truncated"]),
        ),
        "explanation": "Executed a validated read-only AskLens query plan.",
    }
    if run is not None:
        payload["run_id"] = run.pk
    if presentation is not None:
        payload["presentation"] = presentation
    if debug:
        payload["debug"] = {"validated_plan": plan}
    return payload


def build_presentation_payload(
    presentation: PresentationSpec | None,
    *,
    query_result: QueryResult,
    include_presentation: bool,
) -> dict[str, Any] | None:
    """Normalize optional display metadata without changing query execution."""

    if not include_presentation:
        return None
    raw_presentation = (
        presentation.model_dump(mode="json", exclude_none=True)
        if presentation is not None
        else None
    )
    try:
        return dict(
            normalize_presentation(
                raw_presentation,
                columns=query_result.columns,
            )
        )
    except AskLensError:
        return {"kind": "table"}


def build_result_metadata(
    *,
    limit: int,
    limit_scope: str,
    truncated: bool,
) -> dict[str, Any]:
    """Return accurate effective-limit metadata from trusted execution."""

    return {
        "limit": limit,
        "limit_scope": limit_scope,
        "truncated": truncated,
    }


def safe_provider_fallback_message(exc: AskLensError) -> str:
    """Return a provider-fallback reason without raw provider details."""

    if exc.code == "asklens.provider.failed":
        reason = "Provider request failed."
    elif exc.code in {
        "asklens.parse.invalid",
        "asklens.member.unavailable",
        "asklens.plan.invalid",
        "asklens.authorization.denied",
        "asklens.scope.unavailable",
        "asklens.budget.exceeded",
        "asklens.binding.invalid",
        "asklens.compile.failed",
        "asklens.execute.failed",
    }:
        reason = "Provider output failed AskLens validation."
    else:  # pragma: no cover - AskLensErrorCode is exhaustive
        reason = "Provider output could not be used."
    return f"{reason} Returned deterministic AskLens help instead."


def safe_error_category(exc: AskLensError) -> str:
    """Return the stable namespaced public error code."""

    return exc.code


def safe_error_message(exc: AskLensError) -> str:
    """Return the stable safe public error message."""

    return exc.public_message


def safe_error_payload(exc: AskLensError) -> PublicErrorPayload:
    """Return the shared public error object for adapters."""

    return public_error_payload(exc)
