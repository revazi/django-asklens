"""Strict models used to derive draft internal contract JSON Schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from django_asklens.exceptions import AskLensErrorCode
from django_asklens.planning.schemas import (
    DateTrunc,
    FilterOperator,
    Intent,
)

CanonicalType = Literal[
    "string",
    "boolean",
    "integer",
    "decimal",
    "float",
    "date",
    "datetime",
    "time",
    "uuid",
    "enum",
]
NonEmptyString = Annotated[str, Field(min_length=1)]
NonNegativeInteger = Annotated[int, Field(ge=0)]
PositiveInteger = Annotated[int, Field(ge=1)]
JsonCell = str | int | float | bool | None

CONTRACT_MODEL_CONFIG = ConfigDict(extra="forbid", strict=True)


class ContractModel(BaseModel):
    """Base for closed fixed-shape internal contract documents."""

    model_config = CONTRACT_MODEL_CONFIG


class EnumValueDocument(ContractModel):
    """One explicit safe enum value in a catalog."""

    value: str | int
    label: NonEmptyString = None  # type: ignore[assignment]
    aliases: list[str | int] = None  # type: ignore[assignment]


class EnumDocument(ContractModel):
    """Safe enum metadata in a catalog field."""

    type: Literal["string", "integer"]
    values: list[EnumValueDocument] = Field(min_length=1)


class CatalogFieldDocument(ContractModel):
    """One public semantic catalog field."""

    name: NonEmptyString
    label: NonEmptyString
    type: CanonicalType
    nullable: bool
    relation_depth: NonNegativeInteger
    enum: EnumDocument = None  # type: ignore[assignment]
    sensitive: Literal[True] = True
    llm_visible: Literal[False] = False
    result_visible: Literal[False] = False
    filter_only: Literal[True] = True
    scope_dimension: Literal[True] = True


class CatalogMetricDocument(ContractModel):
    """One public registered metric."""

    name: NonEmptyString
    label: NonEmptyString
    result_type: CanonicalType


class DefaultOrderDocument(ContractModel):
    """One deterministic semantic default-order term."""

    field: NonEmptyString
    direction: Literal["asc", "desc"]


class CatalogResourceDocument(ContractModel):
    """One permission-scoped semantic catalog resource."""

    name: NonEmptyString
    label: NonEmptyString
    description: str
    synonyms: list[NonEmptyString]
    default_date_field: NonEmptyString | None
    timezone: NonEmptyString
    fields: list[CatalogFieldDocument]
    metrics: list[CatalogMetricDocument]
    scope_resource: Literal[True] = True
    examples_enabled: Literal[False] = False
    default_order: list[DefaultOrderDocument] = None  # type: ignore[assignment]


class CatalogDocument(ContractModel):
    """Permission-scoped semantic catalog document."""

    resources: list[CatalogResourceDocument]


class TypeCapabilityDocument(ContractModel):
    """Operators supported by one canonical field type."""

    name: CanonicalType
    operators: list[FilterOperator]


class LimitCapabilitiesDocument(ContractModel):
    """Current structural limits advertised by the implementation."""

    max_plan_bytes: PositiveInteger
    max_filters: NonNegativeInteger
    max_selected_fields: NonNegativeInteger
    max_order_terms: NonNegativeInteger
    max_group_terms: NonNegativeInteger
    max_metrics: NonNegativeInteger
    max_relationship_hops: NonNegativeInteger
    max_relationship_edges: NonNegativeInteger
    max_in_values: NonNegativeInteger
    max_filter_values: NonNegativeInteger
    max_result_rows: PositiveInteger
    default_result_limit: PositiveInteger


class FeatureCapabilitiesDocument(ContractModel):
    """Supported and explicitly unsupported implementation features."""

    registered_metrics: bool
    presentation: bool
    accurate_truncation: bool
    raw_sql: bool
    mutations: bool
    cross_resource_queries: bool
    arbitrary_expressions: bool
    cursor_pagination: bool


class AggregatePolicyCapabilitiesDocument(ContractModel):
    """Registered metric relationship policies."""

    to_many_count_policies: list[Literal["count_rows", "count_distinct"]]
    numeric_to_many: bool


class CapabilitiesDocument(ContractModel):
    """Resource-independent implementation capability document."""

    intents: list[Intent]
    filter_logic: Literal["implicit_and"]
    types: list[TypeCapabilityDocument]
    time_grains: list[DateTrunc]
    limits: LimitCapabilitiesDocument
    features: FeatureCapabilitiesDocument
    aggregate_policies: AggregatePolicyCapabilitiesDocument
    backend_restrictions: list[str]


class ResultColumnDocument(ContractModel):
    """One canonical serialized result column."""

    key: NonEmptyString
    label: NonEmptyString
    type: CanonicalType
    nullable: bool


class ResultMetadataDocument(ContractModel):
    """Deterministic execution limit metadata."""

    limit: PositiveInteger
    limit_scope: Literal["rows", "groups"]
    truncated: bool


class ResultDocument(ContractModel):
    """Canonical serialized core query result."""

    columns: list[ResultColumnDocument]
    data: list[dict[str, JsonCell]]
    row_count: NonNegativeInteger
    empty: Literal[True] = True
    duration_ms: NonNegativeInteger
    result_metadata: ResultMetadataDocument


class ErrorDocument(ContractModel):
    """Stable safe public error document."""

    code: AskLensErrorCode
    message: NonEmptyString
    pointer: Annotated[
        str,
        Field(pattern=r"^/[^\x00-\x1f]*$", max_length=200),
    ] = None  # type: ignore[assignment]
