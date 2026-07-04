"""Strict QueryPlan schemas for Django AskLens."""

import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from django_asklens.exceptions import PlanValidationError

type Intent = Literal["list", "aggregate"]
type FilterOperator = Literal[
    "eq",
    "neq",
    "contains",
    "icontains",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "isnull",
    "date_range",
    "last_n_days",
    "last_n_months",
]
type MetricOperator = Literal["count", "sum", "avg", "min", "max"]
type DateTrunc = Literal["day", "week", "month", "quarter", "year"]
type OrderDirection = Literal["asc", "desc"]
type VisualizationType = Literal["table", "metric", "bar", "line", "pie"]
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonScalar] | dict[str, JsonScalar]

PLAN_MODEL_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    validate_default=True,
)


class PlanBaseModel(BaseModel):
    """Base Pydantic model for strict QueryPlan structures."""

    model_config = PLAN_MODEL_CONFIG


class FilterSpec(PlanBaseModel):
    """A filter over a registered resource field."""

    field: str
    op: FilterOperator
    value: JsonValue = None

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        return validate_non_empty_string(value, "filter field")

    @model_validator(mode="after")
    def validate_value_for_operator(self) -> "FilterSpec":
        validate_filter_value(operator=self.op, value=self.value)
        return self


class GroupBySpec(PlanBaseModel):
    """A grouping over a registered resource field."""

    field: str
    date_trunc: DateTrunc | None = None

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        return validate_non_empty_string(value, "group_by field")


class MetricSpec(PlanBaseModel):
    """A metric requested by a plan."""

    name: str
    op: MetricOperator
    field: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_non_empty_string(value, "metric name")

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        return validate_non_empty_string(value, "metric field")


class OrderBySpec(PlanBaseModel):
    """Ordering by either a selected field or a requested metric."""

    field: str | None = None
    metric: str | None = None
    direction: OrderDirection = "asc"

    @field_validator("field", "metric")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_non_empty_string(value, "order_by target")

    @model_validator(mode="after")
    def validate_single_target(self) -> "OrderBySpec":
        has_field = self.field is not None
        has_metric = self.metric is not None
        if has_field == has_metric:
            msg = "order_by must specify exactly one of field or metric."
            raise ValueError(msg)
        return self


class VisualizationSpec(PlanBaseModel):
    """Chart/table hint requested by a plan."""

    type: VisualizationType = "table"
    x: str | None = None
    y: str | None = None

    @field_validator("x", "y")
    @classmethod
    def validate_optional_axis(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_non_empty_string(value, "visualization axis")

    @model_validator(mode="after")
    def validate_axes_for_type(self) -> "VisualizationSpec":
        if self.type in {"bar", "line", "pie"} and (self.x is None or self.y is None):
            msg = f"visualization type {self.type!r} requires x and y."
            raise ValueError(msg)
        if self.type == "metric" and self.y is None:
            msg = "visualization type 'metric' requires y."
            raise ValueError(msg)
        return self


class QueryPlan(PlanBaseModel):
    """Structured, read-only query plan suggested by a planner."""

    resource: str
    intent: Intent
    filters: tuple[FilterSpec, ...] = Field(default_factory=tuple)
    group_by: tuple[GroupBySpec, ...] = Field(default_factory=tuple)
    metrics: tuple[MetricSpec, ...] = Field(default_factory=tuple)
    select: tuple[str, ...] = Field(default_factory=tuple)
    order_by: tuple[OrderBySpec, ...] = Field(default_factory=tuple)
    limit: int = 100
    visualization: VisualizationSpec = Field(default_factory=VisualizationSpec)

    @field_validator("resource")
    @classmethod
    def validate_resource(cls, value: str) -> str:
        return validate_non_empty_string(value, "resource")

    @field_validator("select")
    @classmethod
    def validate_select(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(validate_non_empty_string(item, "select field") for item in value)

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = "limit must be an integer."
            raise ValueError(msg)
        if value < 1:
            msg = "limit must be at least 1."
            raise ValueError(msg)
        return value


def parse_query_plan(raw_plan: str | bytes | Mapping[str, Any]) -> QueryPlan:
    """Parse untrusted JSON/mapping input into a strict QueryPlan."""

    payload = parse_plan_payload(raw_plan)
    try:
        return QueryPlan.model_validate(payload)
    except ValidationError as exc:
        msg = format_pydantic_error(exc)
        raise PlanValidationError(msg) from exc


def parse_plan_payload(raw_plan: str | bytes | Mapping[str, Any]) -> Mapping[str, Any]:
    """Parse raw JSON text or return a mapping payload."""

    if isinstance(raw_plan, Mapping):
        return raw_plan
    if isinstance(raw_plan, bytes):
        raw_plan = raw_plan.decode()
    if isinstance(raw_plan, str):
        try:
            parsed = json.loads(raw_plan)
        except json.JSONDecodeError as exc:
            msg = "QueryPlan payload must be valid JSON."
            raise PlanValidationError(msg) from exc
        if not isinstance(parsed, Mapping):
            msg = "QueryPlan JSON payload must be an object."
            raise PlanValidationError(msg)
        return parsed

    msg = "QueryPlan payload must be a JSON string, bytes, or mapping."
    raise PlanValidationError(msg)


def validate_non_empty_string(value: str, label: str) -> str:
    """Return a stripped non-empty string or raise ValueError."""

    if not isinstance(value, str):
        msg = f"{label} must be a string."
        raise ValueError(msg)
    stripped = value.strip()
    if not stripped:
        msg = f"{label} must not be empty."
        raise ValueError(msg)
    return stripped


def validate_filter_value(*, operator: FilterOperator, value: JsonValue) -> None:
    """Validate a filter value against its operator."""

    if operator == "isnull":
        if not isinstance(value, bool):
            msg = "isnull filters require a boolean value."
            raise ValueError(msg)
        return
    if operator == "in":
        if not isinstance(value, list) or not value:
            msg = "in filters require a non-empty list value."
            raise ValueError(msg)
        return
    if operator == "date_range":
        if not isinstance(value, list) or len(value) != 2:
            msg = "date_range filters require a two-item list value."
            raise ValueError(msg)
        return
    if operator in {"last_n_days", "last_n_months"}:
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            msg = f"{operator} filters require a positive integer value."
            raise ValueError(msg)
        return
    if operator in {"contains", "icontains"}:
        if not isinstance(value, str) or not value:
            msg = f"{operator} filters require a non-empty string value."
            raise ValueError(msg)
        return
    if value is None:
        msg = f"{operator} filters require a value."
        raise ValueError(msg)


def format_pydantic_error(exc: ValidationError) -> str:
    """Return a safe, compact validation error message."""

    first_error = exc.errors(include_input=False)[0]
    location = first_error.get("loc") or ()
    location_text = ".".join(str(part) for part in location) or "query_plan"
    error_message = first_error.get("msg", "Invalid value")
    return f"Invalid QueryPlan at {location_text}: {error_message}."
