"""Private privacy-aware audit policy and sink helpers."""

import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from django.utils import timezone
from django.utils.module_loading import import_string

from django_asklens.exceptions import AskLensError, BindingInvalidError
from django_asklens.settings import get_asklens_setting

type _AuditMode = Literal["database", "disabled", "custom"]
type _AuditEvent = Mapping[str, Any]
type _AuditSink = Callable[[_AuditEvent], Any]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _AuditPolicy:
    """Server-owned audit mode and content policy for one execution."""

    mode: _AuditMode
    include_content: bool


@dataclass(frozen=True, slots=True)
class _AuditContent:
    """Internal content supplied by trusted question orchestration."""

    question: str


_audit_content: ContextVar[_AuditContent | None] = ContextVar(
    "django_asklens_audit_content",
    default=None,
)


@contextmanager
def _execution_audit_content(*, question: str) -> Iterator[None]:
    """Bind optional trusted audit content to one facade call."""

    token = _audit_content.set(_AuditContent(question=question))
    try:
        yield
    finally:
        _audit_content.reset(token)


def _resolve_audit_policy_and_sink(
    *,
    request: Any,
) -> tuple[_AuditPolicy, _AuditSink | None]:
    """Resolve trusted audit configuration for one current request."""

    mode = get_asklens_setting("AUDIT_MODE")
    if mode not in {"database", "disabled", "custom"}:
        msg = "DJANGO_ASKLENS['AUDIT_MODE'] must be database, disabled, or custom."
        raise BindingInvalidError(msg)

    include_content = get_asklens_setting("AUDIT_INCLUDE_CONTENT")
    if not isinstance(include_content, bool):
        msg = "DJANGO_ASKLENS['AUDIT_INCLUDE_CONTENT'] must be a boolean."
        raise BindingInvalidError(msg)

    policy = _AuditPolicy(mode=mode, include_content=include_content)
    if mode == "disabled":
        return policy, None
    if mode == "database":
        return policy, lambda event: _write_database_audit(event, request=request)

    configured_sink = get_asklens_setting("AUDIT_SINK")
    if isinstance(configured_sink, str):
        configured_sink = import_string(configured_sink)
    if not callable(configured_sink):
        msg = "DJANGO_ASKLENS['AUDIT_SINK'] must be callable in custom mode."
        raise BindingInvalidError(msg)
    return policy, configured_sink


def _build_audit_event(
    *,
    policy: _AuditPolicy,
    timestamp: datetime,
    principal: Any,
    resource: str | None,
    intent: str | None,
    status: str,
    row_count: int,
    duration_ms: int | None,
    error: AskLensError | None,
    validated_plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build safe operational metadata plus explicitly opted-in content."""

    principal_id = getattr(principal, "pk", None)
    event: dict[str, Any] = {
        "timestamp": timestamp,
        "principal_id": principal_id,
        "resource": resource,
        "intent": intent,
        "status": status,
        "row_count": row_count,
        "duration_ms": duration_ms,
        "error_code": error.code if error is not None else None,
        "error_message": error.public_message if error is not None else "",
    }
    if policy.include_content:
        content = _audit_content.get()
        event["question"] = content.question if content is not None else ""
        event["plan"] = dict(validated_plan or {})
    return event


def _emit_audit_event(
    *,
    sink: _AuditSink | None,
    event: _AuditEvent,
) -> Any:
    """Emit at most once and never let audit failure broaden execution."""

    if sink is None:
        return None
    try:
        return sink(event)
    except Exception:
        logger.exception("AskLens audit sink failed.")
        return None


def _audit_external_rejection(
    *,
    request: Any,
    error: AskLensError,
) -> Any:
    """Audit a provider/orchestration rejection that precedes facade execution."""

    try:
        policy, sink = _resolve_audit_policy_and_sink(request=request)
    except AskLensError:
        return None
    event = _build_audit_event(
        policy=policy,
        timestamp=timezone.now(),
        principal=getattr(request, "user", None),
        resource=None,
        intent=None,
        status="failed",
        row_count=0,
        duration_ms=None,
        error=error,
        validated_plan=None,
    )
    return _emit_audit_event(sink=sink, event=event)


def _write_database_audit(event: _AuditEvent, *, request: Any) -> Any:
    """Persist one AskLens-owned metadata audit row."""

    from django_asklens.models import SemanticQueryRun

    principal = getattr(request, "user", None)
    user = (
        principal
        if getattr(principal, "is_authenticated", False)
        and getattr(principal, "pk", None) is not None
        else None
    )
    if "plan" in event:
        plan = dict(event["plan"])
        question = str(event.get("question", ""))
    else:
        plan = {
            key: value
            for key, value in {
                "resource": event.get("resource"),
                "intent": event.get("intent"),
            }.items()
            if value is not None
        }
        question = ""

    error_code = event.get("error_code")
    error_message = str(event.get("error_message", ""))
    error = f"{error_code}: {error_message}" if error_code else ""
    return SemanticQueryRun.objects.create(
        user=user,
        question=question,
        plan=plan,
        status=str(event["status"]),
        row_count=int(event["row_count"]),
        duration_ms=event.get("duration_ms"),
        error=error,
    )
