"""DRF serializers for the AskLens API."""

import re
from collections.abc import Mapping
from typing import Any

from rest_framework import serializers

from django_asklens.exceptions import (
    AuthorizationDeniedError,
    BindingInvalidError,
    BudgetExceededError,
    CompilationError,
    ExecutionError,
    LLMProviderError,
    PermissionDeniedError,
    PlanParseError,
    PlanValidationError,
    ScopeUnavailableError,
)
from django_asklens.models import SemanticQueryRun
from django_asklens.settings import get_asklens_setting

_SAFE_AUDIT_ERRORS = {
    PlanParseError.code: PlanParseError.public_message,
    PermissionDeniedError.code: PermissionDeniedError.public_message,
    PlanValidationError.code: PlanValidationError.public_message,
    AuthorizationDeniedError.code: AuthorizationDeniedError.public_message,
    ScopeUnavailableError.code: ScopeUnavailableError.public_message,
    BudgetExceededError.code: BudgetExceededError.public_message,
    BindingInvalidError.code: BindingInvalidError.public_message,
    CompilationError.code: CompilationError.public_message,
    ExecutionError.code: ExecutionError.public_message,
    LLMProviderError.code: LLMProviderError.public_message,
}
_GENERIC_AUDIT_ERROR = {
    "code": ExecutionError.code,
    "message": ExecutionError.public_message,
}
_SAFE_RESOURCE_NAME = re.compile(r"[a-z0-9_]+\Z")
_SAFE_AUDIT_INTENTS = frozenset({"list", "aggregate"})


class QueryRequestSerializer(serializers.Serializer):
    """Validate the strict query endpoint input object."""

    question = serializers.CharField(allow_blank=False, trim_whitespace=True)
    debug = serializers.BooleanField(default=False, required=False)
    include_presentation = serializers.BooleanField(default=True, required=False)
    plan = serializers.JSONField(required=False)
    presentation = serializers.JSONField(required=False)

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        """Reject unknown top-level fields without reflecting their content."""

        if isinstance(data, Mapping) and any(key not in self.fields for key in data):
            raise serializers.ValidationError(
                "The query request contains unsupported fields.",
                code="unknown",
            )
        return super().to_internal_value(data)


class SemanticQueryRunSerializer(serializers.ModelSerializer):
    """Serialize query-run audit records under the current privacy policy."""

    question = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()

    class Meta:
        model = SemanticQueryRun
        fields = (
            "id",
            "question",
            "plan",
            "status",
            "row_count",
            "duration_ms",
            "error",
            "created_at",
        )
        read_only_fields = fields

    def get_question(self, run: SemanticQueryRun) -> str:
        """Return retained question content only under explicit current opt-in."""

        if get_asklens_setting("AUDIT_INCLUDE_CONTENT") is True:
            return run.question
        return ""

    def get_plan(self, run: SemanticQueryRun) -> Any:
        """Return full retained plan content or bounded operational metadata."""

        if get_asklens_setting("AUDIT_INCLUDE_CONTENT") is True:
            return run.plan
        if not isinstance(run.plan, Mapping):
            return {}

        operational_plan: dict[str, str] = {}
        resource = run.plan.get("resource")
        if (
            isinstance(resource, str)
            and len(resource) <= 200
            and _SAFE_RESOURCE_NAME.fullmatch(resource) is not None
        ):
            operational_plan["resource"] = resource
        intent = run.plan.get("intent")
        if isinstance(intent, str) and intent in _SAFE_AUDIT_INTENTS:
            operational_plan["intent"] = intent
        return operational_plan

    def get_error(self, run: SemanticQueryRun) -> dict[str, str] | None:
        """Derive a structured safe error without reflecting stored free text."""

        if run.status == SemanticQueryRun.Status.SUCCESS or not run.error.strip():
            return None
        for code, message in _SAFE_AUDIT_ERRORS.items():
            if run.error == f"{code}: {message}":
                return {"code": code, "message": message}
        return dict(_GENERIC_AUDIT_ERROR)
