"""Semantic catalog resource definitions."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Literal, NotRequired, TypedDict

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import QuerySet
from django.utils.text import slugify

from django_asklens.catalog.introspection import (
    FieldResolution,
    get_field_type,
    resolve_field_path,
)
from django_asklens.exceptions import (
    InvalidMetricError,
    InvalidResourceError,
    ScopeUnavailableError,
    UnknownFieldError,
)
from django_asklens.settings import get_asklens_setting

type MetricOp = Literal["count", "sum", "avg", "min", "max"]
type MetricCardinalityPolicy = Literal["to_one_only", "count_rows", "count_distinct"]
type FieldConfig = Mapping[str, object]
type ScopeMode = Literal["global", "context_scoped"]
type ResourceOrderDirection = Literal["asc", "desc"]
type DefaultOrder = tuple[tuple[str, ResourceOrderDirection], ...]
type ScopeProvider = Callable[[Any], QuerySet]
type BaseQuerySetHook = Callable[[Any], QuerySet]

_BASE_QUERYSET_UNSET = object()


class MetricCatalogItem(TypedDict):
    """Serialized metric metadata included in catalog output."""

    name: str
    label: str
    result_type: str


class EnumValueCatalogItem(TypedDict):
    """One safe registered enum value exposed to catalog consumers."""

    value: str | int
    label: NotRequired[str]
    aliases: NotRequired[list[str | int]]


class EnumCatalogItem(TypedDict):
    """Safe explicit enum metadata exposed to catalog consumers."""

    type: Literal["string", "integer"]
    values: list[EnumValueCatalogItem]


class FieldCatalogItem(TypedDict):
    """Serialized field metadata included in catalog output."""

    name: str
    label: str
    type: str
    nullable: bool
    relation_depth: int
    enum: NotRequired[EnumCatalogItem]
    sensitive: NotRequired[bool]
    llm_visible: NotRequired[bool]
    result_visible: NotRequired[bool]
    filter_only: NotRequired[bool]
    scope_dimension: NotRequired[bool]


class ResourceCatalogItem(TypedDict):
    """Serialized resource metadata included in catalog output."""

    name: str
    label: str
    description: str
    synonyms: list[str]
    default_date_field: str | None
    fields: list[FieldCatalogItem]
    metrics: list[MetricCatalogItem]
    scope_resource: NotRequired[bool]
    examples_enabled: NotRequired[bool]
    default_order: NotRequired[list[dict[str, str]]]


class CatalogSnapshot(TypedDict):
    """Serialized semantic catalog output."""

    resources: list[ResourceCatalogItem]


SUPPORTED_METRIC_OPS = {"count", "sum", "avg", "min", "max"}
OPERATORS_BY_FIELD_TYPE: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "string": ("eq", "neq", "contains", "icontains", "in", "isnull"),
        "boolean": ("eq", "neq", "in", "isnull"),
        "integer": ("eq", "neq", "gt", "gte", "lt", "lte", "in", "isnull"),
        "decimal": ("eq", "neq", "gt", "gte", "lt", "lte", "in", "isnull"),
        "float": ("eq", "neq", "gt", "gte", "lt", "lte", "in", "isnull"),
        "date": (
            "eq",
            "neq",
            "gt",
            "gte",
            "lt",
            "lte",
            "in",
            "isnull",
            "date_range",
            "last_n_days",
            "last_n_months",
        ),
        "datetime": (
            "eq",
            "neq",
            "gt",
            "gte",
            "lt",
            "lte",
            "in",
            "isnull",
            "date_range",
            "last_n_days",
            "last_n_months",
        ),
        "time": ("eq", "neq", "gt", "gte", "lt", "lte", "in", "isnull"),
        "uuid": ("eq", "neq", "in", "isnull"),
        "enum": ("eq", "neq", "in", "isnull"),
    }
)
SUPPORTED_METRIC_CARDINALITY_POLICIES = {
    "to_one_only",
    "count_rows",
    "count_distinct",
}
NUMERIC_FIELD_TYPES = {"decimal", "float", "integer"}
SUPPORTED_FIELD_TYPES = {
    "boolean",
    "date",
    "datetime",
    "decimal",
    "enum",
    "float",
    "integer",
    "string",
    "time",
    "uuid",
}
ALLOWED_FIELD_CONFIG_KEYS = {
    "binding",
    "enum",
    "filter_only",
    "label",
    "llm_visible",
    "nullable",
    "requires_permission",
    "result_visible",
    "sensitive",
    "scope_dimension",
    "type",
}
DATE_FIELD_TYPES = {"date", "datetime"}


@dataclass(frozen=True, slots=True)
class EnumValue:
    """One immutable canonical enum value and its accepted aliases."""

    value: str | int
    label: str | None = None
    aliases: tuple[str | int, ...] = ()

    def to_dict(self) -> EnumValueCatalogItem:
        """Serialize only explicitly registered safe enum metadata."""

        data: EnumValueCatalogItem = {"value": self.value}
        if self.label is not None:
            data["label"] = self.label
        if self.aliases:
            data["aliases"] = list(self.aliases)
        return data


@dataclass(frozen=True, slots=True)
class EnumDefinition:
    """Immutable explicit enum definition for one semantic field."""

    type: Literal["string", "integer"]
    values: tuple[EnumValue, ...]

    def to_dict(self) -> EnumCatalogItem:
        """Serialize this safe semantic enum definition."""

        return {
            "type": self.type,
            "values": [value.to_dict() for value in self.values],
        }


@dataclass(frozen=True, slots=True)
class Metric:
    """Developer-registered aggregate with trusted private backing metadata."""

    name: str
    op: MetricOp
    binding: str = field(repr=False)
    result_type: str
    label: str | None = None
    cardinality_policy: MetricCardinalityPolicy = "to_one_only"
    distinct_key: str | None = field(default=None, repr=False)
    requires_permission: str | None = field(default=None, repr=False)
    relation_depth: int = field(default=0, repr=False, compare=False)
    relationship_edges: tuple[str, ...] = field(default=(), repr=False, compare=False)
    to_many_relationship_edges: tuple[str, ...] = field(
        default=(), repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name
            or "__" in self.name
            or any(part == "" for part in self.name.split("."))
        ):
            msg = (
                "Metric name must be a non-empty semantic key without '__' or "
                "empty dotted segments."
            )
            raise InvalidMetricError(msg)
        if not isinstance(self.op, str) or self.op not in SUPPORTED_METRIC_OPS:
            msg = f"Unsupported metric operation {self.op!r} for metric {self.name!r}."
            raise InvalidMetricError(msg)
        if not isinstance(self.binding, str) or not self.binding:
            msg = f"Metric {self.name!r} requires a private binding."
            raise InvalidMetricError(msg)
        if (
            not isinstance(self.result_type, str)
            or self.result_type not in SUPPORTED_FIELD_TYPES
        ):
            msg = f"Metric {self.name!r} requires a supported canonical result_type."
            raise InvalidMetricError(msg)
        if self.label is not None and not isinstance(self.label, str):
            msg = f"Metric {self.name!r} label must be a string."
            raise InvalidMetricError(msg)
        if (
            not isinstance(self.cardinality_policy, str)
            or self.cardinality_policy not in SUPPORTED_METRIC_CARDINALITY_POLICIES
        ):
            msg = (
                f"Unsupported cardinality policy {self.cardinality_policy!r} "
                f"for metric {self.name!r}."
            )
            raise InvalidMetricError(msg)
        if self.distinct_key is not None and (
            not isinstance(self.distinct_key, str) or not self.distinct_key
        ):
            msg = f"Metric {self.name!r} distinct_key must be a non-empty string."
            raise InvalidMetricError(msg)
        if self.requires_permission is not None and not isinstance(
            self.requires_permission, str
        ):
            msg = f"Metric {self.name!r} requires_permission must be a string."
            raise InvalidMetricError(msg)

    def is_catalog_visible(self, permissions: Iterable[str] = ()) -> bool:
        """Return whether current trusted permissions expose this metric."""

        return permission_set_allows(permissions, self.requires_permission)

    def to_dict(self) -> MetricCatalogItem:
        """Serialize only safe semantic metric metadata."""

        return {
            "name": self.name,
            "label": self.label or self.name.replace("_", " ").title(),
            "result_type": self.result_type,
        }


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Developer-allowed semantic field with a private Django binding."""

    name: str
    label: str
    type: str
    nullable: bool
    binding: str = field(repr=False)
    relation_depth: int = field(repr=False)
    relationship_edges: tuple[str, ...] = field(default=(), repr=False)
    to_many_relationship_edges: tuple[str, ...] = field(default=(), repr=False)
    enum: EnumDefinition | None = None
    sensitive: bool = False
    llm_visible: bool = True
    result_visible: bool = True
    filter_only: bool = False
    requires_permission: str | None = None
    scope_dimension: bool = False

    def is_catalog_visible(
        self,
        *,
        include_sensitive: bool,
        include_hidden: bool,
        permissions: Iterable[str] | None = None,
    ) -> bool:
        """Return whether this field belongs in serialized catalog output."""

        permission_set = frozenset(permissions or ())
        permission_allowed = (
            self.requires_permission is None
            or permission_set_allows(permission_set, self.requires_permission)
            or (self.sensitive and include_sensitive)
        )
        sensitive_allowed = include_sensitive or (
            self.sensitive
            and self.requires_permission is not None
            and permission_set_allows(permission_set, self.requires_permission)
        )
        hidden_allowed = include_hidden or (self.sensitive and sensitive_allowed)

        if not permission_allowed:
            return False
        if self.sensitive and not sensitive_allowed:
            return False
        if not self.llm_visible and not hidden_allowed:
            return False
        return True

    def to_dict(self) -> FieldCatalogItem:
        """Serialize the field for catalog consumers."""

        data: FieldCatalogItem = {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "nullable": self.nullable,
            "relation_depth": self.relation_depth,
        }
        if self.enum is not None:
            data["enum"] = self.enum.to_dict()
        if self.sensitive:
            data["sensitive"] = True
        if not self.llm_visible:
            data["llm_visible"] = False
        if not self.result_visible:
            data["result_visible"] = False
        if self.filter_only:
            data["filter_only"] = True
        if self.scope_dimension:
            data["scope_dimension"] = True
        return data


@dataclass(frozen=True, slots=True)
class SemanticResource:
    """A developer-registered model/resource exposed to AskLens."""

    model: type[models.Model]
    name: str
    label: str
    scope_mode: ScopeMode
    description: str = ""
    synonyms: tuple[str, ...] = ()
    default_date_field: str | None = None
    fields: Mapping[str, FieldSpec] = field(default_factory=dict)
    metrics: Mapping[str, Metric] = field(default_factory=dict)
    default_order: DefaultOrder = ()
    row_identity: str = ""
    scope_provider: ScopeProvider | None = None
    requires_permission: str | None = None
    scope_resource: bool = False
    examples_enabled: bool = True

    def __post_init__(self) -> None:
        """Store resource metadata as effectively immutable mappings."""

        validate_scope_policy(
            scope_mode=self.scope_mode,
            scope_provider=self.scope_provider,
        )
        normalized_order = normalize_default_order(
            self.default_order,
            fields=self.fields,
        )
        normalized_identity = validate_row_identity(
            self.model,
            self.row_identity or None,
        )
        object.__setattr__(self, "default_order", normalized_order)
        object.__setattr__(self, "row_identity", normalized_identity)
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))

    @classmethod
    def build(
        cls,
        *,
        model: type[models.Model],
        fields: Mapping[str, FieldConfig | FieldSpec],
        name: str | None = None,
        label: str | None = None,
        description: str = "",
        synonyms: Sequence[str] | None = None,
        default_date_field: str | None = None,
        metrics: Sequence[Metric] | None = None,
        scope_mode: ScopeMode | None = None,
        scope_provider: ScopeProvider | None = None,
        default_order: Sequence[tuple[str, str]] | None = None,
        row_identity: str | None = None,
        base_queryset: BaseQuerySetHook | None | object = _BASE_QUERYSET_UNSET,
        requires_permission: str | None = None,
        scope_resource: bool = False,
        examples_enabled: bool = True,
    ) -> "SemanticResource":
        """Build and validate a semantic resource from developer configuration."""

        validate_model(model)
        validate_legacy_base_queryset(base_queryset)
        validated_scope_mode = validate_scope_policy(
            scope_mode=resolve_scope_mode(scope_mode),
            scope_provider=scope_provider,
        )
        validate_requires_permission(requires_permission)
        validate_scope_resource(scope_resource)
        validate_examples_enabled(examples_enabled)

        resource_label = label or str(model._meta.verbose_name_plural).title()
        resource_name = normalize_resource_name(name or resource_label)
        field_specs = build_field_specs(model=model, fields=fields)

        validate_default_date_field(
            model=model,
            resource_name=resource_name,
            field_specs=field_specs,
            default_date_field=default_date_field,
        )

        metric_specs = build_metric_specs(model=model, metrics=metrics or ())
        normalized_synonyms = normalize_synonyms(synonyms or ())
        normalized_order = normalize_default_order(
            default_order if default_order is not None else (),
            fields=field_specs,
        )
        normalized_identity = validate_row_identity(model, row_identity)

        return cls(
            model=model,
            name=resource_name,
            label=resource_label,
            scope_mode=validated_scope_mode,
            description=description,
            synonyms=normalized_synonyms,
            default_date_field=default_date_field,
            fields=field_specs,
            metrics=metric_specs,
            default_order=normalized_order,
            row_identity=normalized_identity,
            scope_provider=scope_provider,
            requires_permission=requires_permission,
            scope_resource=scope_resource,
            examples_enabled=examples_enabled,
        )

    def get_scope_queryset(self, request: Any) -> QuerySet:
        """Resolve the explicitly declared resource scope without evaluating it."""

        if self.scope_mode == "global":
            return self.model._default_manager.all()
        if request is None:
            msg = "Context-scoped resources require the current request."
            raise ScopeUnavailableError(msg)
        if self.scope_provider is None:  # Defensive against invalid manual mutation.
            msg = "The context-scoped resource has no scope provider."
            raise ScopeUnavailableError(msg)

        try:
            queryset = self.scope_provider(request)
        except Exception as exc:
            msg = "The current resource scope provider failed."
            raise ScopeUnavailableError(msg) from exc

        if not isinstance(queryset, QuerySet):
            msg = "The current resource scope provider must return a QuerySet."
            raise ScopeUnavailableError(msg)
        if queryset.model is not self.model:
            msg = "The current resource scope QuerySet has the wrong registered model."
            raise ScopeUnavailableError(msg)
        # QuerySet exposes no public evaluated-state API; a populated result
        # cache proves the provider did not return the required lazy scope.
        if queryset._result_cache is not None:
            msg = "The current resource scope provider returned an evaluated QuerySet."
            raise ScopeUnavailableError(msg)
        return queryset

    def is_catalog_visible(self, *, permissions: Iterable[str] | None = None) -> bool:
        """Return whether this resource belongs in permission-scoped catalog output."""

        return permission_set_allows(permissions or (), self.requires_permission)

    def to_dict(
        self,
        *,
        include_sensitive: bool = False,
        include_hidden: bool = False,
        permissions: Iterable[str] | None = None,
    ) -> ResourceCatalogItem:
        """Serialize safe catalog metadata for planners/API consumers."""

        permission_set = frozenset(permissions or ())
        visible_fields: list[FieldCatalogItem] = [
            field_spec.to_dict()
            for field_spec in self.fields.values()
            if field_spec.is_catalog_visible(
                include_sensitive=include_sensitive,
                include_hidden=include_hidden,
                permissions=permission_set,
            )
        ]
        visible_metrics: list[MetricCatalogItem] = [
            metric.to_dict()
            for metric in self.metrics.values()
            if metric.is_catalog_visible(permission_set)
        ]

        data: ResourceCatalogItem = {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "synonyms": list(self.synonyms),
            "default_date_field": self.default_date_field,
            "fields": visible_fields,
            "metrics": visible_metrics,
        }
        if self.scope_resource:
            data["scope_resource"] = True
        if not self.examples_enabled:
            data["examples_enabled"] = False
        if self.default_order:
            data["default_order"] = [
                {"field": field_name, "direction": direction}
                for field_name, direction in self.default_order
            ]
        return data


def permission_set_allows(
    permissions: Iterable[str], required_permission: str | None
) -> bool:
    """Return whether permission tokens include a required permission.

    Exact permission strings are accepted. Scoped permission tokens that end with
    ``:<required_permission>`` are also accepted so projects can return values
    shaped as ``<scope-kind>:<opaque-scope-id>:<required_permission>`` from a
    request-permission hook while AskLens still validates against the registered
    field permission name.
    Row-level access must still be enforced by context-scoped resource providers.
    """

    if required_permission is None:
        return True
    permission_set = frozenset(permissions)
    if required_permission in permission_set:
        return True
    scoped_suffix = f":{required_permission}"
    return any(permission.endswith(scoped_suffix) for permission in permission_set)


def normalize_resource_name(value: str) -> str:
    """Normalize a developer-facing resource name for plan references."""

    normalized = slugify(value).replace("-", "_")
    if not normalized:
        msg = f"Invalid resource name {value!r}."
        raise InvalidResourceError(msg)
    return normalized


def validate_model(model: object) -> None:
    """Validate that a resource model is a Django model class."""

    if not isinstance(model, type) or not issubclass(model, models.Model):
        msg = "Semantic resources must be registered with a Django model class."
        raise InvalidResourceError(msg)


def validate_legacy_base_queryset(
    base_queryset: BaseQuerySetHook | None | object,
) -> None:
    """Reject any use of the legacy scope hook with migration guidance."""

    if base_queryset is not _BASE_QUERYSET_UNSET:
        msg = (
            "base_queryset is no longer supported; use "
            "scope_mode='context_scoped' and scope_provider=... instead."
        )
        raise InvalidResourceError(msg)


def resolve_scope_mode(scope_mode: object) -> object:
    """Resolve a safe project default while keeping global scope explicit."""

    default_scope_mode = get_asklens_setting("DEFAULT_SCOPE_MODE")
    if default_scope_mode not in (None, "context_scoped"):
        msg = (
            "DJANGO_ASKLENS['DEFAULT_SCOPE_MODE'] must be 'context_scoped' or "
            "None; global resources must declare scope_mode='global' explicitly."
        )
        raise InvalidResourceError(msg)
    if scope_mode is not None:
        return scope_mode
    return default_scope_mode


def validate_scope_policy(
    *,
    scope_mode: object,
    scope_provider: object,
) -> ScopeMode:
    """Validate and normalize explicit fail-closed resource scope policy."""

    if scope_mode is None:
        msg = "scope_mode is required; choose 'global' or 'context_scoped'."
        raise InvalidResourceError(msg)
    if scope_mode not in ("global", "context_scoped"):
        msg = "scope_mode must be 'global' or 'context_scoped'."
        raise InvalidResourceError(msg)
    if scope_mode == "global":
        if scope_provider is not None:
            msg = "A global resource must not define scope_provider."
            raise InvalidResourceError(msg)
        return "global"
    if scope_provider is None:
        msg = "A context_scoped resource requires scope_provider."
        raise InvalidResourceError(msg)
    if not callable(scope_provider):
        msg = "scope_provider must be callable for a context_scoped resource."
        raise InvalidResourceError(msg)
    return "context_scoped"


def normalize_default_order(
    default_order: Sequence[tuple[str, str]],
    *,
    fields: Mapping[str, FieldSpec],
) -> DefaultOrder:
    """Validate semantic default ordering against registered fields."""

    if isinstance(default_order, (str, bytes)):
        msg = "default_order must be a sequence of (field, direction) pairs."
        raise InvalidResourceError(msg)

    normalized: list[tuple[str, ResourceOrderDirection]] = []
    seen: set[str] = set()
    for item in default_order:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            msg = "default_order entries must be (field, direction) pairs."
            raise InvalidResourceError(msg)
        field_name, direction = item
        if not isinstance(field_name, str) or field_name not in fields:
            msg = "default_order must reference registered semantic fields."
            raise InvalidResourceError(msg)
        field_spec = fields[field_name]
        if (
            field_spec.sensitive
            or not field_spec.llm_visible
            or not field_spec.result_visible
            or field_spec.filter_only
            or field_spec.requires_permission is not None
        ):
            msg = "default_order must use unrestricted result-visible fields."
            raise InvalidResourceError(msg)
        if field_name in seen:
            msg = f"Duplicate default_order field {field_name!r}."
            raise InvalidResourceError(msg)
        if direction not in ("asc", "desc"):
            msg = "default_order direction must be 'asc' or 'desc'."
            raise InvalidResourceError(msg)
        seen.add(field_name)
        normalized.append((field_name, direction))
    return tuple(normalized)


def validate_row_identity(
    model: type[models.Model],
    row_identity: str | None,
) -> str:
    """Return a private non-null unique field usable as a stable tie-breaker."""

    identity = model._meta.pk.name if row_identity is None else row_identity
    if not isinstance(identity, str) or not identity or "." in identity:
        msg = "row_identity must name one concrete field on the registered model."
        raise InvalidResourceError(msg)
    try:
        identity_field = model._meta.get_field(identity)
    except FieldDoesNotExist as exc:
        msg = "row_identity must name one concrete field on the registered model."
        raise InvalidResourceError(msg) from exc
    if not isinstance(identity_field, models.Field) or not identity_field.concrete:
        msg = "row_identity must name one concrete field on the registered model."
        raise InvalidResourceError(msg)
    if identity_field.null:
        msg = "row_identity must have a non-null unconditional unique constraint."
        raise InvalidResourceError(msg)
    if identity_field.primary_key or identity_field.unique:
        return identity

    unique_together = tuple(model._meta.unique_together or ())
    if (identity,) in unique_together:
        return identity
    for constraint in model._meta.constraints:
        if not isinstance(constraint, models.UniqueConstraint):
            continue
        if constraint.condition is not None or constraint.expressions:
            continue
        if tuple(constraint.fields) == (identity,):
            return identity

    msg = "row_identity must have a non-null unconditional unique constraint."
    raise InvalidResourceError(msg)


def validate_requires_permission(requires_permission: str | None) -> None:
    """Validate optional resource-level permission metadata."""

    if requires_permission is not None and not isinstance(requires_permission, str):
        msg = "requires_permission must be a string when provided."
        raise InvalidResourceError(msg)


def validate_scope_resource(scope_resource: bool) -> None:
    """Validate resource-level scope metadata."""

    if not isinstance(scope_resource, bool):
        msg = "scope_resource must be a boolean when provided."
        raise InvalidResourceError(msg)


def validate_examples_enabled(examples_enabled: bool) -> None:
    """Validate resource example-generation metadata."""

    if not isinstance(examples_enabled, bool):
        msg = "examples_enabled must be a boolean when provided."
        raise InvalidResourceError(msg)


def validate_default_date_field(
    *,
    model: type[models.Model],
    resource_name: str,
    field_specs: Mapping[str, FieldSpec],
    default_date_field: str | None,
) -> None:
    """Validate the optional default date field for a resource."""

    if default_date_field is None:
        return
    if default_date_field not in field_specs:
        msg = (
            f"Default date field {default_date_field!r} must be included in "
            f"the allowed fields for resource {resource_name!r}."
        )
        raise UnknownFieldError(msg)

    field_spec = field_specs[default_date_field]
    binding_field_type = get_field_type(
        resolve_field_path(model, field_spec.binding).field
    )
    if (
        field_spec.type not in DATE_FIELD_TYPES
        or binding_field_type not in DATE_FIELD_TYPES
    ):
        msg = (
            f"Default date field {default_date_field!r} must be a date "
            f"or datetime field for resource {resource_name!r}."
        )
        raise InvalidResourceError(msg)


def normalize_synonyms(synonyms: Sequence[str]) -> tuple[str, ...]:
    """Validate and normalize resource synonyms."""

    if isinstance(synonyms, str):
        msg = "synonyms must be a sequence of strings, not a single string."
        raise InvalidResourceError(msg)

    normalized: list[str] = []
    for synonym in synonyms:
        if not isinstance(synonym, str):
            msg = "synonyms must contain only strings."
            raise InvalidResourceError(msg)
        stripped = synonym.strip()
        if stripped:
            normalized.append(stripped)
    return tuple(normalized)


def validate_semantic_field_key(key: object) -> str:
    """Validate a public field key without giving it ORM-path meaning."""

    if not isinstance(key, str) or not key or "__" in key:
        msg = "Semantic field keys must be non-empty strings without '__'."
        raise InvalidResourceError(msg)
    if any(part == "" for part in key.split(".")):
        msg = f"Semantic field key {key!r} contains an empty dotted segment."
        raise InvalidResourceError(msg)
    return key


def validate_field_spec(
    key: str,
    field_spec: FieldSpec,
    *,
    relation_depth: int,
    relationship_edges: tuple[str, ...],
    to_many_relationship_edges: tuple[str, ...],
    binding_type: str,
    binding_nullable: bool,
) -> FieldSpec:
    """Validate and normalize a prebuilt semantic field specification."""

    if field_spec.name != key:
        msg = f"FieldSpec name {field_spec.name!r} must match semantic key {key!r}."
        raise InvalidResourceError(msg)
    if not field_spec.type:
        msg = f"FieldSpec type is required for semantic key {key!r}."
        raise InvalidResourceError(msg)
    if field_spec.type not in SUPPORTED_FIELD_TYPES:
        msg = f"Unsupported canonical type {field_spec.type!r} for field {key!r}."
        raise InvalidResourceError(msg)
    validate_binding_type(
        key, configured_type=field_spec.type, binding_type=binding_type
    )
    enum_definition = validate_enum_definition(
        key,
        configured_type=field_spec.type,
        binding_type=binding_type,
        raw_definition=field_spec.enum,
    )
    if not isinstance(field_spec.nullable, bool):
        msg = f"FieldSpec nullable must be a boolean for semantic key {key!r}."
        raise InvalidResourceError(msg)
    if binding_nullable and not field_spec.nullable:
        msg = f"Semantic field {key!r} cannot be non-null for its nullable binding."
        raise InvalidResourceError(msg)
    return replace(
        field_spec,
        relation_depth=relation_depth,
        relationship_edges=relationship_edges,
        to_many_relationship_edges=to_many_relationship_edges,
        enum=enum_definition,
    )


def validate_binding_type(
    key: str,
    *,
    configured_type: str,
    binding_type: str,
) -> None:
    """Reject semantic types incompatible with resolved Django field types."""

    if configured_type == binding_type:
        return
    if configured_type == "enum" and binding_type in {"integer", "string"}:
        return
    msg = (
        f"Canonical type {configured_type!r} for field {key!r} does not match "
        f"its private binding type {binding_type!r}."
    )
    raise InvalidResourceError(msg)


def validate_enum_definition(
    key: str,
    *,
    configured_type: str,
    binding_type: str,
    raw_definition: object,
) -> EnumDefinition | None:
    """Validate explicit enum metadata without inspecting Django choices."""

    if configured_type != "enum":
        if raw_definition is not None:
            msg = f"Enum metadata is only supported for canonical type 'enum': {key!r}."
            raise InvalidResourceError(msg)
        return None
    if raw_definition is None:
        msg = f"Canonical enum field {key!r} requires explicit enum metadata."
        raise InvalidResourceError(msg)

    if isinstance(raw_definition, EnumDefinition):
        definition: object = raw_definition.to_dict()
    else:
        definition = raw_definition
    if not isinstance(definition, Mapping):
        msg = f"Enum metadata for field {key!r} must be a mapping."
        raise InvalidResourceError(msg)
    unknown_definition_keys = set(definition) - {"type", "values"}
    if unknown_definition_keys:
        msg = f"Unknown enum metadata keys for field {key!r}."
        raise InvalidResourceError(msg)

    underlying_type = definition.get("type")
    if underlying_type not in {"string", "integer"}:
        msg = f"Enum field {key!r} type must be 'string' or 'integer'."
        raise InvalidResourceError(msg)
    if underlying_type != binding_type:
        msg = (
            f"Enum underlying type {underlying_type!r} for field {key!r} does not "
            f"match its private binding type {binding_type!r}."
        )
        raise InvalidResourceError(msg)

    raw_values = definition.get("values")
    if (
        not isinstance(raw_values, Sequence)
        or isinstance(raw_values, (str, bytes))
        or not raw_values
    ):
        msg = f"Enum field {key!r} requires a non-empty values sequence."
        raise InvalidResourceError(msg)

    values: list[EnumValue] = []
    canonical_keys: set[tuple[type[object], object]] = set()
    accepted_tokens: dict[tuple[type[object], object], object] = {}
    for raw_value in raw_values:
        if not isinstance(raw_value, Mapping):
            msg = f"Enum values for field {key!r} must be mappings."
            raise InvalidResourceError(msg)
        if set(raw_value) - {"value", "label", "aliases"}:
            msg = f"Unknown enum value metadata keys for field {key!r}."
            raise InvalidResourceError(msg)

        canonical = raw_value.get("value")
        validate_enum_scalar(
            canonical,
            underlying_type=underlying_type,
            key=key,
            label="canonical value",
        )
        canonical_key = enum_token_key(canonical)
        if canonical_key in canonical_keys:
            msg = f"Duplicate canonical enum value for field {key!r}."
            raise InvalidResourceError(msg)
        canonical_keys.add(canonical_key)

        label = raw_value.get("label")
        if label is not None and (not isinstance(label, str) or not label.strip()):
            msg = f"Enum labels for field {key!r} must be non-empty strings."
            raise InvalidResourceError(msg)

        raw_aliases = raw_value.get("aliases", ())
        if not isinstance(raw_aliases, Sequence) or isinstance(
            raw_aliases, (str, bytes)
        ):
            msg = f"Enum aliases for field {key!r} must be a sequence."
            raise InvalidResourceError(msg)
        aliases: list[str | int] = []
        for alias in raw_aliases:
            validate_enum_alias(alias, key=key)
            aliases.append(alias)

        for token in (canonical, *aliases):
            token_key = enum_token_key(token)
            existing = accepted_tokens.get(token_key)
            if existing is not None and enum_token_key(existing) != canonical_key:
                msg = f"Ambiguous enum alias for field {key!r}."
                raise InvalidResourceError(msg)
            accepted_tokens[token_key] = canonical

        values.append(
            EnumValue(
                value=canonical,
                label=label.strip() if isinstance(label, str) else None,
                aliases=tuple(aliases),
            )
        )

    return EnumDefinition(type=underlying_type, values=tuple(values))


def validate_enum_scalar(
    value: object,
    *,
    underlying_type: str,
    key: str,
    label: str,
) -> None:
    """Validate one canonical enum scalar against its declared type."""

    if underlying_type == "string":
        if not isinstance(value, str) or not value:
            msg = f"Enum {label} for field {key!r} must be a non-empty string."
            raise InvalidResourceError(msg)
        return
    if not isinstance(value, int) or isinstance(value, bool):
        msg = f"Enum {label} for field {key!r} must be an integer."
        raise InvalidResourceError(msg)


def validate_enum_alias(value: object, *, key: str) -> None:
    """Validate one explicit enum input alias."""

    if isinstance(value, bool) or not isinstance(value, (str, int)):
        msg = f"Enum aliases for field {key!r} must be strings or integers."
        raise InvalidResourceError(msg)
    if isinstance(value, str) and not value:
        msg = f"Enum aliases for field {key!r} must not be empty."
        raise InvalidResourceError(msg)


def enum_token_key(value: object) -> tuple[type[object], object]:
    """Return a type-aware enum token key so booleans never alias integers."""

    return (type(value), value)


def get_bool_field_config(
    field_config: Mapping[str, Any],
    key: str,
    *,
    default: bool,
) -> bool:
    """Return a boolean field-config value with strict type checking."""

    value = field_config.get(key, default)
    if not isinstance(value, bool):
        msg = f"Field config key {key!r} must be a boolean."
        raise InvalidResourceError(msg)
    return value


def build_field_specs(
    *, model: type[models.Model], fields: Mapping[str, FieldConfig | FieldSpec]
) -> dict[str, FieldSpec]:
    """Validate and normalize explicit field allowlist configuration."""

    if not isinstance(fields, Mapping) or not fields:
        msg = f"Resource {model._meta.label} must declare at least one allowed field."
        raise InvalidResourceError(msg)

    field_specs: dict[str, FieldSpec] = {}
    for raw_key, config in fields.items():
        key = validate_semantic_field_key(raw_key)
        if isinstance(config, FieldSpec):
            if not config.binding:
                msg = f"Private binding is required for semantic field {key!r}."
                raise InvalidResourceError(msg)
            resolution = resolve_field_path(model, config.binding)
            field_specs[key] = validate_field_spec(
                key,
                config,
                relation_depth=resolution.relation_depth,
                relationship_edges=resolution.relationship_edges,
                to_many_relationship_edges=resolution.to_many_relationship_edges,
                binding_type=get_field_type(resolution.field),
                binding_nullable=resolution.nullable,
            )
            continue

        if not isinstance(config, Mapping):
            msg = f"Field config for semantic key {key!r} must be a mapping."
            raise InvalidResourceError(msg)

        field_config = dict(config)
        unknown_keys = set(field_config) - ALLOWED_FIELD_CONFIG_KEYS
        if "metric" in unknown_keys:
            msg = (
                f"Field config key 'metric' is no longer supported for {key!r}; "
                "define a Metric with a private binding and result_type instead."
            )
            raise InvalidResourceError(msg)
        if unknown_keys:
            unknown_keys_display = ", ".join(sorted(unknown_keys))
            msg = f"Unknown field config keys for {key!r}: {unknown_keys_display}."
            raise InvalidResourceError(msg)

        binding = field_config.get("binding")
        if not isinstance(binding, str) or not binding:
            msg = (
                f"Private binding is required for semantic field {key!r}; add "
                "binding='field' or binding='relation__field'."
            )
            raise InvalidResourceError(msg)
        resolution = resolve_field_path(model, binding)

        configured_type = field_config.get("type")
        if not isinstance(configured_type, str) or not configured_type:
            msg = f"Canonical type is required for semantic field {key!r}."
            raise InvalidResourceError(msg)
        if configured_type not in SUPPORTED_FIELD_TYPES:
            msg = f"Unsupported canonical type {configured_type!r} for field {key!r}."
            raise InvalidResourceError(msg)
        binding_type = get_field_type(resolution.field)
        validate_binding_type(
            key,
            configured_type=configured_type,
            binding_type=binding_type,
        )
        enum_definition = validate_enum_definition(
            key,
            configured_type=configured_type,
            binding_type=binding_type,
            raw_definition=field_config.get("enum"),
        )
        configured_nullable = field_config.get("nullable")
        if not isinstance(configured_nullable, bool):
            msg = f"nullable must be a boolean for semantic field {key!r}."
            raise InvalidResourceError(msg)
        if resolution.nullable and not configured_nullable:
            msg = f"Semantic field {key!r} cannot be non-null for its nullable binding."
            raise InvalidResourceError(msg)

        sensitive = get_bool_field_config(field_config, "sensitive", default=False)
        llm_visible = get_bool_field_config(
            field_config,
            "llm_visible",
            default=not sensitive,
        )
        result_visible = get_bool_field_config(
            field_config,
            "result_visible",
            default=not sensitive,
        )
        label = str(field_config.get("label") or default_field_label(key))
        requires_permission = field_config.get("requires_permission")
        if requires_permission is not None and not isinstance(requires_permission, str):
            msg = f"requires_permission for {key!r} must be a string."
            raise InvalidResourceError(msg)

        field_specs[key] = FieldSpec(
            name=key,
            label=label,
            type=configured_type,
            nullable=configured_nullable,
            binding=binding,
            relation_depth=resolution.relation_depth,
            relationship_edges=resolution.relationship_edges,
            to_many_relationship_edges=resolution.to_many_relationship_edges,
            enum=enum_definition,
            sensitive=sensitive,
            llm_visible=llm_visible,
            result_visible=result_visible,
            filter_only=get_bool_field_config(
                field_config,
                "filter_only",
                default=False,
            ),
            requires_permission=requires_permission,
            scope_dimension=get_bool_field_config(
                field_config,
                "scope_dimension",
                default=False,
            ),
        )

    return field_specs


def build_metric_specs(
    *, model: type[models.Model], metrics: Sequence[Metric]
) -> dict[str, Metric]:
    """Resolve trusted metric bindings and reject unsafe cardinality."""

    metric_specs: dict[str, Metric] = {}
    for metric in metrics:
        if not isinstance(metric, Metric):
            msg = "metrics must contain Metric registrations."
            raise InvalidMetricError(msg)
        if metric.name in metric_specs:
            msg = f"Duplicate metric name {metric.name!r}."
            raise InvalidMetricError(msg)

        resolution = resolve_field_path(model, metric.binding)
        binding_type = get_field_type(resolution.field)
        validate_metric_result_type(metric, binding_type=binding_type)
        validate_metric_cardinality(model, metric, resolution=resolution)

        bound_resolutions = [resolution]
        if metric.cardinality_policy == "count_distinct" and metric.distinct_key:
            bound_resolutions.append(resolve_field_path(model, metric.distinct_key))
        metric_specs[metric.name] = replace(
            metric,
            relation_depth=max(item.relation_depth for item in bound_resolutions),
            relationship_edges=dedupe_relationship_edges(
                edge for item in bound_resolutions for edge in item.relationship_edges
            ),
            to_many_relationship_edges=dedupe_relationship_edges(
                edge
                for item in bound_resolutions
                for edge in item.to_many_relationship_edges
            ),
        )
    return metric_specs


def dedupe_relationship_edges(edges: Iterable[str]) -> tuple[str, ...]:
    """Preserve trusted relationship order while removing repeated prefixes."""

    return tuple(dict.fromkeys(edges))


def validate_metric_result_type(metric: Metric, *, binding_type: str) -> None:
    """Reject registrations whose trusted operation/type pair is contradictory."""

    if metric.op == "count":
        if metric.result_type != "integer":
            msg = f"Count metric {metric.name!r} must use result_type='integer'."
            raise InvalidMetricError(msg)
        return
    if metric.op in {"sum", "avg"}:
        if binding_type not in NUMERIC_FIELD_TYPES:
            msg = f"Metric {metric.name!r} requires a numeric private binding."
            raise InvalidMetricError(msg)
        expected_type = (
            "float"
            if metric.op == "avg" and binding_type == "integer"
            else binding_type
        )
        if metric.result_type != expected_type:
            msg = (
                f"Metric {metric.name!r} result_type must be {expected_type!r} "
                f"for its private binding."
            )
            raise InvalidMetricError(msg)
        return
    if metric.result_type != binding_type:
        msg = (
            f"Metric {metric.name!r} result_type must match its private "
            f"binding type {binding_type!r}."
        )
        raise InvalidMetricError(msg)


def validate_metric_cardinality(
    model: type[models.Model],
    metric: Metric,
    *,
    resolution: FieldResolution,
) -> None:
    """Enforce the accepted fail-closed metric fanout policies."""

    to_many_edges = resolution.to_many_relationship_edges
    if metric.op in {"sum", "avg", "min", "max"} and to_many_edges:
        msg = f"Numeric metric {metric.name!r} cannot cross a to-many relationship."
        raise InvalidMetricError(msg)

    if metric.cardinality_policy == "to_one_only":
        if metric.distinct_key is not None:
            msg = f"Metric {metric.name!r} must not define distinct_key."
            raise InvalidMetricError(msg)
        if to_many_edges:
            msg = f"Metric {metric.name!r} cannot cross a to-many relationship."
            raise InvalidMetricError(msg)
        return

    if metric.op != "count":
        msg = f"Metric policy {metric.cardinality_policy!r} requires op='count'."
        raise InvalidMetricError(msg)
    if len(to_many_edges) != 1:
        msg = (
            f"Metric {metric.name!r} must cross exactly one to-many relationship "
            f"for policy {metric.cardinality_policy!r}."
        )
        raise InvalidMetricError(msg)

    if metric.cardinality_policy == "count_rows":
        if metric.distinct_key is not None:
            msg = f"count_rows metric {metric.name!r} must not define distinct_key."
            raise InvalidMetricError(msg)
        validate_private_metric_key(metric.name, resolution.field, label="binding")
        return

    if not metric.distinct_key:
        msg = f"count_distinct metric {metric.name!r} requires distinct_key."
        raise InvalidMetricError(msg)
    distinct_resolution = resolve_field_path(model, metric.distinct_key)
    if distinct_resolution.to_many_relationship_edges != to_many_edges:
        msg = (
            f"count_distinct metric {metric.name!r} must use a distinct_key at "
            "the same declared to-many grain as its binding."
        )
        raise InvalidMetricError(msg)
    validate_private_metric_key(
        metric.name,
        distinct_resolution.field,
        label="distinct_key",
    )


def validate_private_metric_key(
    metric_name: str,
    metric_field: object,
    *,
    label: str,
) -> None:
    """Require a non-null unique concrete key for an explicit count grain."""

    if (
        not isinstance(metric_field, models.Field)
        or not metric_field.concrete
        or metric_field.null
    ):
        msg = (
            f"Metric {metric_name!r} {label} must resolve to a non-null unique "
            "concrete field."
        )
        raise InvalidMetricError(msg)
    if metric_field.primary_key or metric_field.unique:
        return

    model = metric_field.model
    field_name = metric_field.name
    if (field_name,) in tuple(model._meta.unique_together or ()):
        return
    for constraint in model._meta.constraints:
        if not isinstance(constraint, models.UniqueConstraint):
            continue
        if constraint.condition is not None or constraint.expressions:
            continue
        if tuple(constraint.fields) == (field_name,):
            return

    msg = (
        f"Metric {metric_name!r} {label} must resolve to a non-null unique "
        "concrete field."
    )
    raise InvalidMetricError(msg)


def default_field_label(key: str) -> str:
    """Return a binding-independent label for a public semantic key."""

    return key.replace(".", " ").replace("_", " ").title()
