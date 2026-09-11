"""Independent packaged-schema evidence for containment value constraints."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError

from django_asklens import get_contract_schema
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import (
    PlanParseError,
    PublicAskLensError,
    public_error_payload,
)
from django_asklens.execution import execute_plan
from django_asklens.planning.schemas import parse_query_plan


def _plan(operator: str, value: object) -> dict[str, Any]:
    """Return a structural example, not a catalog-authorized executable plan."""

    return {
        "resource": "orders",
        "intent": "list",
        "filters": [{"field": "status", "op": operator, "value": value}],
    }


@pytest.mark.parametrize("operator", ["contains", "icontains"])
@pytest.mark.parametrize("value", ["", 1, True], ids=["empty", "integer", "boolean"])
def test_packaged_schema_rejects_containment_values_rejected_by_parser(
    operator: str, value: object
) -> None:
    """Exercise the actual JSON file rather than its generating Pydantic model."""

    plan = _plan(operator, value)
    with pytest.raises(PlanParseError):
        parse_query_plan(plan)
    validator = Draft202012Validator(get_contract_schema("query-plan"))
    with pytest.raises(SchemaValidationError):
        validator.validate(plan)


@pytest.mark.parametrize("operator", ["contains", "icontains"])
@pytest.mark.parametrize("value", ["paid", " ", "東京"])
def test_containment_preserves_nonempty_strings(operator: str, value: str) -> None:
    """Whitespace and Unicode remain legal values; this is not semantic validation."""

    plan = _plan(operator, value)
    parsed = parse_query_plan(plan)
    assert parsed.filters[0].value == value
    validator = Draft202012Validator(get_contract_schema("query-plan"))
    validator.validate(plan)
    validator.validate(parsed.model_dump(mode="json"))


@pytest.mark.parametrize("operator", ["eq", "neq", "gt", "gte", "lt", "lte"])
@pytest.mark.parametrize("value", ["", "paid", 1, 1.5, True])
def test_scalar_comparisons_are_not_tightened_with_containment(
    operator: str, value: object
) -> None:
    """Comparison shape stays scalar; catalog-dependent type checks happen later."""

    plan = _plan(operator, value)
    parsed = parse_query_plan(plan)
    assert parsed.filters[0].value == value
    Draft202012Validator(get_contract_schema("query-plan")).validate(plan)


@pytest.mark.django_db
@pytest.mark.postgresql
@pytest.mark.parametrize("operator", ["contains", "icontains"])
@pytest.mark.parametrize("value", ["", 1, True], ids=["empty", "integer", "boolean"])
def test_invalid_containment_stops_before_preparation_and_sql(
    operator: str,
    value: object,
    settings: Any,
    django_assert_num_queries: Any,
) -> None:
    """Facade rejection is unchanged, opaque, and SQL-free with audit disabled."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}
    with (
        django_assert_num_queries(0),
        patch("django_asklens.execution.runner._prepare_query_plan") as prepare,
        pytest.raises(PublicAskLensError) as raised,
    ):
        execute_plan(
            _plan(operator, value),
            request=SimpleNamespace(user=None),
            registry=CatalogRegistry(),
        )
    prepare.assert_not_called()
    assert public_error_payload(raised.value) == {
        "code": "asklens.parse.invalid",
        "message": "The query plan could not be parsed.",
    }
