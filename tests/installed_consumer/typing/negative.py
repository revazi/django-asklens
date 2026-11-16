"""Every marked line must fail with exactly the specified mypy error code."""

from django.db.models import Model

from django_asklens import Metric, get_resource, register
from django_asklens.catalog import CatalogRegistry
from django_asklens.exceptions import PublicAskLensError, public_error_payload
from django_asklens.execution import QueryResult, execute_plan
from django_asklens.observability import ObservabilityEvent


def incorrect_registration(model: type[Model]) -> None:
    Metric(name="n", op="median", binding="id", result_type="integer")  # E: arg-type
    Metric(name="n", op="count", binding=12, result_type="integer")  # E: arg-type
    register(model=model, fields={}, name=42)  # E: arg-type
    register(model=model, fields=["id"])  # E: arg-type
    register(model=model, fields={}, metrics=["count"])  # E: list-item
    register(model=model, fields={}, scope_mode="automatic")  # E: arg-type
    register(model=model, fields={}, scope_provider=42)  # E: arg-type
    CatalogRegistry().register(model=model, fields={}, timezone=42)  # E: arg-type
    get_resource(42)  # E: arg-type


def incorrect_execution(request: object) -> None:
    execute_plan(42, request=request)  # E: arg-type
    execute_plan("{}")  # E: call-arg
    execute_plan("{}", request=request, registry={})  # E: arg-type


def incorrect_result(result: QueryResult) -> None:
    _text: str = result.row_count  # E: assignment
    _count: int = result.rows  # E: assignment
    result.rows.append({})  # E: attr-defined
    result.row_count = 3  # E: misc
    result.to_dict("extra")  # E: call-arg
    _ = result.missing_accessor  # E: attr-defined


def incorrect_error(exc: PublicAskLensError) -> None:
    public_error_payload("unsafe text")  # E: arg-type
    public_error_payload(exc)["code"] = "arbitrary"  # E: typeddict-item
    _pointer: int = exc.pointer  # E: assignment


def incorrect_observation(event: ObservabilityEvent) -> None:
    event.duration_ms = 0  # E: misc
    _count: int = event.result_count  # E: assignment
    _ = event.missing_field  # E: attr-defined
