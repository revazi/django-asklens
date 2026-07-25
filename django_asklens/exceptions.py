"""Typed internal exceptions and stable public AskLens error shapes."""

from typing import Literal, NotRequired, TypedDict

type AskLensErrorCode = Literal[
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
]


class PublicErrorPayload(TypedDict):
    """Safe serialized error fields shared by every public adapter."""

    code: AskLensErrorCode
    message: str
    pointer: NotRequired[str]


class AskLensError(Exception):
    """Base exception carrying internal detail and stable public metadata."""

    code: AskLensErrorCode = "asklens.execute.failed"
    public_message = "The AskLens request could not be completed."

    def __init__(self, message: str = "", *, pointer: str | None = None) -> None:
        self.diagnostic_message = message
        self.pointer = pointer
        super().__init__(message)


class PublicAskLensError(AskLensError):
    """Safe Python exception exposed by the trusted execution facade."""

    def __init__(self, source: AskLensError) -> None:
        self.code = source.code
        self.public_message = source.public_message
        self._audit_record = None
        self._audit_attempted = False
        super().__init__(
            source.public_message, pointer=safe_json_pointer(source.pointer)
        )


class CatalogError(AskLensError):
    """Base exception for semantic catalog errors."""

    code = "asklens.binding.invalid"
    public_message = "The semantic catalog contains an invalid binding."


class DuplicateResourceError(CatalogError):
    """Raised when a semantic resource name is already registered."""


class UnknownResourceError(CatalogError):
    """Raised when a semantic resource cannot be found."""

    code = "asklens.member.unavailable"
    public_message = "A requested query member is unavailable."


class UnknownFieldError(CatalogError):
    """Raised when a configured or requested field cannot be found."""

    code = "asklens.member.unavailable"
    public_message = "A requested query member is unavailable."


class InvalidResourceError(CatalogError):
    """Raised when a semantic resource configuration is invalid."""


class InvalidMetricError(CatalogError):
    """Raised when a metric configuration is invalid."""


class PlanValidationError(AskLensError):
    """Raised when a QueryPlan is semantically invalid or unsafe."""

    code = "asklens.plan.invalid"
    public_message = "The query plan is invalid."


class PlanParseError(PlanValidationError):
    """Raised when untrusted QueryPlan input cannot be parsed structurally."""

    code = "asklens.parse.invalid"
    public_message = "The query plan could not be parsed."


class BudgetExceededError(PlanValidationError):
    """Raised when a QueryPlan exceeds a configured structural limit."""

    code = "asklens.budget.exceeded"
    public_message = "The query plan exceeds an execution limit."


class UnknownMetricError(PlanValidationError):
    """Raised when a QueryPlan references an unavailable metric."""

    code = "asklens.member.unavailable"
    public_message = "A requested query member is unavailable."


class PermissionDeniedError(AskLensError):
    """Raised when a requested resource or field is unavailable to the caller."""

    code = "asklens.member.unavailable"
    public_message = "A requested query member is unavailable."


class AuthorizationDeniedError(AskLensError):
    """Raised when current trusted request authorization is unavailable."""

    code = "asklens.authorization.denied"
    public_message = "The current request is not authorized to execute this query."


class ScopeUnavailableError(AskLensError):
    """Raised when trusted current-request row scope cannot be resolved."""

    code = "asklens.scope.unavailable"
    public_message = "A safe query scope is unavailable for this request."


class BindingInvalidError(AskLensError):
    """Raised when validated semantics cannot be bound safely."""

    code = "asklens.binding.invalid"
    public_message = "The query plan could not be bound safely."


class CompilationError(AskLensError):
    """Raised when a prepared plan cannot be compiled to the Django ORM."""

    code = "asklens.compile.failed"
    public_message = "The query plan could not be compiled."


class ExecutionError(AskLensError):
    """Raised when a private compiled Django ORM query cannot be evaluated."""

    code = "asklens.execute.failed"
    public_message = "The query could not be executed."


class UnsupportedQueryError(PlanValidationError):
    """Raised when a QueryPlan asks for unsupported behavior."""


class LLMProviderError(AskLensError):
    """Raised when an LLM provider cannot return a usable response."""

    code = "asklens.provider.failed"
    public_message = "The query provider could not produce a usable response."


class ResultSerializationError(ExecutionError):
    """Raised when result data cannot be serialized safely."""


class VisualizationHintError(ResultSerializationError):
    """Raised when visualization hint metadata is invalid."""


def safe_json_pointer(pointer: str | None) -> str | None:
    """Return a bounded safe JSON Pointer or omit an unsafe value."""

    if pointer is None or not pointer.startswith("/") or len(pointer) > 200:
        return None
    if any(ord(character) < 32 for character in pointer):
        return None
    return pointer


def public_error_payload(exc: AskLensError) -> PublicErrorPayload:
    """Return only a stable code, safe message, and optional safe pointer."""

    payload: PublicErrorPayload = {
        "code": exc.code,
        "message": exc.public_message,
    }
    pointer = safe_json_pointer(exc.pointer)
    if pointer is not None:
        payload["pointer"] = pointer
    return payload


def normalize_public_error(exc: AskLensError) -> PublicAskLensError:
    """Return a safe Python exception without retaining diagnostic text."""

    if isinstance(exc, PublicAskLensError):
        return exc
    return PublicAskLensError(exc)
