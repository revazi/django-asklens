"""Privacy-safe host observability for trusted AskLens lifecycle outcomes."""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from typing import Literal

from django.db import connections, transaction
from django.utils.module_loading import import_string

from django_asklens.exceptions import AskLensErrorCode
from django_asklens.settings import get_asklens_setting

type ObservabilityEventName = Literal[
    "asklens.plan.accepted",
    "asklens.plan.rejected",
    "asklens.execution.succeeded",
    "asklens.execution.failed",
]
type ObservabilityStatus = Literal["accepted", "rejected", "succeeded", "failed"]
type ObservabilityIntent = Literal["list", "aggregate"]
type _ObservabilitySink = Callable[["ObservabilityEvent"], object]

_EVENT_STATUSES: dict[str, str] = {
    "asklens.plan.accepted": "accepted",
    "asklens.plan.rejected": "rejected",
    "asklens.execution.succeeded": "succeeded",
    "asklens.execution.failed": "failed",
}
_ERROR_CODES = frozenset(
    {
        "asklens.parse.invalid",
        "asklens.member.unavailable",
        "asklens.plan.invalid",
        "asklens.authorization.denied",
        "asklens.scope.unavailable",
        "asklens.budget.exceeded",
        "asklens.binding.invalid",
        "asklens.compile.failed",
        "asklens.execute.failed",
        "asklens.provider.failed",
    }
)
_emitting: ContextVar[bool] = ContextVar(
    "django_asklens_observability_emitting",
    default=False,
)
_defer_context_rejection: ContextVar[bool] = ContextVar(
    "django_asklens_observability_defer_context_rejection",
    default=False,
)

__all__ = ["ObservabilityEvent"]


@dataclass(frozen=True, slots=True)
class ObservabilityEvent:
    """One immutable, content-free trusted lifecycle observation.

    Hosts should treat ``resource``, ``intent``, ``status``, and ``error_code``
    as bounded labels. Durations and result counts are measurements, not labels.
    """

    name: ObservabilityEventName
    status: ObservabilityStatus
    resource: str | None
    intent: ObservabilityIntent | None
    error_code: AskLensErrorCode | None
    duration_ms: int
    result_count: int | None
    truncated: bool | None

    def __post_init__(self) -> None:
        """Reject unknown values and invalid lifecycle field combinations."""

        if not isinstance(self.name, str) or not isinstance(self.status, str):
            msg = "Observability event name and status must be strings."
            raise ValueError(msg)
        expected_status = _EVENT_STATUSES.get(self.name)
        if expected_status is None or self.status != expected_status:
            msg = "Invalid AskLens observability event name/status combination."
            raise ValueError(msg)
        if (
            not isinstance(self.duration_ms, int)
            or isinstance(self.duration_ms, bool)
            or self.duration_ms < 0
        ):
            msg = "Observability duration_ms must be a non-negative integer."
            raise ValueError(msg)

        has_resolved_plan = self.name != "asklens.plan.rejected"
        if has_resolved_plan:
            if not isinstance(self.resource, str) or not self.resource:
                msg = "Resolved observability events require a resource."
                raise ValueError(msg)
            if not isinstance(self.intent, str) or self.intent not in {
                "list",
                "aggregate",
            }:
                msg = "Resolved observability events require a canonical intent."
                raise ValueError(msg)
        elif self.resource is not None or self.intent is not None:
            msg = "Rejected-plan observations cannot include untrusted names."
            raise ValueError(msg)

        is_failure = self.status in {"rejected", "failed"}
        if is_failure != (self.error_code is not None):
            msg = "Observability failures require exactly one canonical error code."
            raise ValueError(msg)
        if self.error_code is not None and (
            not isinstance(self.error_code, str) or self.error_code not in _ERROR_CODES
        ):
            msg = "Unknown AskLens observability error code."
            raise ValueError(msg)

        if self.name == "asklens.execution.succeeded":
            if (
                not isinstance(self.result_count, int)
                or isinstance(self.result_count, bool)
                or self.result_count < 0
                or not isinstance(self.truncated, bool)
            ):
                msg = "Successful execution observations require result metadata."
                raise ValueError(msg)
        elif self.result_count is not None or self.truncated is not None:
            msg = "Only successful execution observations include result metadata."
            raise ValueError(msg)


def _build_observability_event(
    *,
    name: ObservabilityEventName,
    status: ObservabilityStatus,
    resource: str | None,
    intent: ObservabilityIntent | None,
    error_code: AskLensErrorCode | None,
    duration_ms: int,
    result_count: int | None,
    truncated: bool | None,
) -> ObservabilityEvent | None:
    """Build one event without allowing instrumentation to alter execution."""

    try:
        return ObservabilityEvent(
            name=name,
            status=status,
            resource=resource,
            intent=intent,
            error_code=error_code,
            duration_ms=duration_ms,
            result_count=result_count,
            truncated=truncated,
        )
    except (TypeError, ValueError):
        return None


def _resolve_observability_sink() -> _ObservabilitySink | None:
    """Resolve optional host configuration without affecting query behavior."""

    try:
        configured_sink = get_asklens_setting("OBSERVABILITY_SINK")
        if configured_sink is None:
            return None
        if isinstance(configured_sink, str):
            configured_sink = import_string(configured_sink)
        return configured_sink if callable(configured_sink) else None
    except Exception:
        return None


def _emit_observability_events(
    *,
    sink: _ObservabilitySink | None,
    events: Iterable[ObservabilityEvent],
) -> None:
    """Deliver outside caller transactions; suppress sink errors and recursion."""

    if sink is None or _emitting.get():
        return
    try:
        pending_events = tuple(events)
    except Exception:
        return
    if not pending_events:
        return

    def deliver() -> None:
        for event in pending_events:
            token = _emitting.set(True)
            try:
                sink(event)
            except Exception:
                return
            finally:
                _emitting.reset(token)

    _after_open_transactions(deliver)


def _after_open_transactions(callback: Callable[[], None]) -> None:
    """Run only after every current Django atomic block commits successfully."""

    try:
        active_connections = []
        for connection in connections.all(initialized_only=True):
            # Accessing get_autocommit() opens a wrapper that has been looked up
            # but never connected. Unopened aliases cannot own a transaction
            # and observability must not add a connection or query.
            if connection.connection is None or connection.get_autocommit():
                continue
            if not connection.in_atomic_block:
                # Django provides no public post-commit hook for manual
                # transaction management. Dropping best-effort observations is
                # safer than running host code inside an authoritative
                # transaction or relying on database-backend internals.
                return
            active_connections.append(connection)

        if not active_connections:
            callback()
            return

        # Register against every transaction that is active now. Registering
        # sequentially through just one connection would lose the knowledge
        # that another connection rolled back before the first one committed.
        # A rollback discards that connection's on_commit callback, leaving the
        # barrier incomplete and therefore dropping the observation batch.
        state = {"remaining": len(active_connections), "cancelled": False}
        state_lock = Lock()

        def connection_committed() -> None:
            with state_lock:
                state["remaining"] -= 1
                ready = state["remaining"] == 0 and not state["cancelled"]
            if ready:
                callback()

        try:
            for connection in active_connections:
                transaction.on_commit(connection_committed, using=connection.alias)
        except Exception:
            # A partial registration must never become a partial delivery.
            with state_lock:
                state["cancelled"] = True
    except Exception:
        # Instrumentation and callback scheduling are both non-authoritative.
        return


@contextmanager
def _defer_context_rejection_observability() -> Iterator[None]:
    """Let shared orchestration audit a pre-plan rejection before observing it."""

    token = _defer_context_rejection.set(True)
    try:
        yield
    finally:
        _defer_context_rejection.reset(token)


def _context_rejection_observability_is_deferred() -> bool:
    """Return whether shared orchestration owns the current pre-plan outcome."""

    return _defer_context_rejection.get()


def _emit_external_plan_rejection(
    *,
    error_code: AskLensErrorCode,
    duration_ms: int,
) -> None:
    """Observe a final pre-facade orchestration rejection without input names."""

    event = _build_observability_event(
        name="asklens.plan.rejected",
        status="rejected",
        resource=None,
        intent=None,
        error_code=error_code,
        duration_ms=duration_ms,
        result_count=None,
        truncated=None,
    )
    if event is None:
        return
    _emit_observability_events(
        sink=_resolve_observability_sink(),
        events=(event,),
    )
