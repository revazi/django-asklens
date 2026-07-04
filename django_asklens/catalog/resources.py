"""Semantic catalog resource definitions."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, NotRequired, TypedDict

from django.db import models
from django.db.models import QuerySet
from django.utils.text import slugify

from django_asklens.catalog.introspection import get_field_type, resolve_field_path
from django_asklens.exceptions import (
    InvalidMetricError,
    InvalidResourceError,
    UnknownFieldError,
)

type MetricOp = Literal["count", "sum", "avg", "min", "max"]
type FieldConfig = Mapping[str, str | bool | None]
type BaseQuerySetHook = Callable[[Any], QuerySet]


class MetricCatalogItem(TypedDict):
    """Serialized metric metadata included in catalog output."""

    name: str
    label: str
    op: MetricOp
    field: str


class FieldCatalogItem(TypedDict):
    """Serialized field metadata included in catalog output."""

    name: str
    label: str
    type: str
    relation_depth: int
    sensitive: NotRequired[bool]
    llm_visible: NotRequired[bool]
    result_visible: NotRequired[bool]
    filter_only: NotRequired[bool]
    requires_permission: NotRequired[str]
    metric: NotRequired[bool]


class ResourceCatalogItem(TypedDict):
    """Serialized resource metadata included in catalog output."""

    name: str
    label: str
    description: str
    synonyms: list[str]
    default_date_field: str | None
    fields: list[FieldCatalogItem]
    metrics: list[MetricCatalogItem]
    model: NotRequired[str]


class CatalogSnapshot(TypedDict):
    """Serialized semantic catalog output."""

    resources: list[ResourceCatalogItem]


SUPPORTED_METRIC_OPS = {"count", "sum", "avg", "min", "max"}
ALLOWED_FIELD_CONFIG_KEYS = {
    "filter_only",
    "label",
    "llm_visible",
    "metric",
    "requires_permission",
    "result_visible",
    "sensitive",
    "type",
}
DATE_FIELD_TYPES = {"date", "datetime"}


@dataclass(frozen=True, slots=True)
class Metric:
    """Developer-registered aggregate metric."""

    name: str
    op: MetricOp
    field: str
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            msg = "Metric name is required."
            raise InvalidMetricError(msg)
        if self.op not in SUPPORTED_METRIC_OPS:
            msg = f"Unsupported metric operation {self.op!r} for metric {self.name!r}."
            raise InvalidMetricError(msg)
        if not self.field:
            msg = f"Metric {self.name!r} requires a field."
            raise InvalidMetricError(msg)

    def to_dict(self) -> MetricCatalogItem:
        """Serialize the metric for catalog consumers."""

        return {
            "name": self.name,
            "label": self.label or self.name.replace("_", " ").title(),
            "op": self.op,
            "field": self.field,
        }


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Developer-allowed field metadata for a semantic resource."""

    name: str
    label: str
    type: str
    relation_depth: int
    sensitive: bool = False
    llm_visible: bool = True
    result_visible: bool = True
    filter_only: bool = False
    requires_permission: str | None = None
    metric: bool = False

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
            or self.requires_permission in permission_set
            or (self.sensitive and include_sensitive)
        )
        sensitive_allowed = include_sensitive or (
            self.sensitive
            and self.requires_permission is not None
            and self.requires_permission in permission_set
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
            "relation_depth": self.relation_depth,
        }
        if self.sensitive:
            data["sensitive"] = True
        if not self.llm_visible:
            data["llm_visible"] = False
        if not self.result_visible:
            data["result_visible"] = False
        if self.filter_only:
            data["filter_only"] = True
        if self.requires_permission:
            data["requires_permission"] = self.requires_permission
        if self.metric:
            data["metric"] = True
        return data


@dataclass(frozen=True, slots=True)
class SemanticResource:
    """A developer-registered model/resource exposed to AskLens."""

    model: type[models.Model]
    name: str
    label: str
    description: str = ""
    synonyms: tuple[str, ...] = ()
    default_date_field: str | None = None
    fields: Mapping[str, FieldSpec] = field(default_factory=dict)
    metrics: Mapping[str, Metric] = field(default_factory=dict)
    base_queryset: BaseQuerySetHook | None = None

    def __post_init__(self) -> None:
        """Store resource metadata as effectively immutable mappings."""

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
        base_queryset: BaseQuerySetHook | None = None,
    ) -> "SemanticResource":
        """Build and validate a semantic resource from developer configuration."""

        validate_model(model)
        validate_base_queryset(base_queryset)

        resource_label = label or str(model._meta.verbose_name_plural).title()
        resource_name = normalize_resource_name(name or resource_label)
        field_specs = build_field_specs(model=model, fields=fields)

        validate_default_date_field(
            model=model,
            resource_name=resource_name,
            field_specs=field_specs,
            default_date_field=default_date_field,
        )

        metric_specs = build_metric_specs(metrics=metrics or (), fields=field_specs)
        normalized_synonyms = normalize_synonyms(synonyms or ())

        return cls(
            model=model,
            name=resource_name,
            label=resource_label,
            description=description,
            synonyms=normalized_synonyms,
            default_date_field=default_date_field,
            fields=field_specs,
            metrics=metric_specs,
            base_queryset=base_queryset,
        )

    def get_base_queryset(self, request: Any = None) -> QuerySet:
        """Return the base queryset for this resource."""

        if self.base_queryset is not None:
            return self.base_queryset(request)
        return self.model._default_manager.all()

    def to_dict(
        self,
        *,
        include_sensitive: bool = False,
        include_hidden: bool = False,
        include_internal: bool = False,
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
        visible_field_names = {field["name"] for field in visible_fields}
        visible_metrics: list[MetricCatalogItem] = [
            metric.to_dict()
            for metric in self.metrics.values()
            if metric.field in visible_field_names
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
        if include_internal:
            data["model"] = self.model._meta.label
        return data


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


def validate_base_queryset(base_queryset: BaseQuerySetHook | None) -> None:
    """Validate an optional base-queryset hook."""

    if base_queryset is not None and not callable(base_queryset):
        msg = "base_queryset must be callable when provided."
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

    default_field_type = get_field_type(
        resolve_field_path(model, default_date_field).field
    )
    if default_field_type not in DATE_FIELD_TYPES:
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


def validate_field_spec(
    path: str,
    field_spec: FieldSpec,
    relation_depth: int,
) -> FieldSpec:
    """Validate a prebuilt field spec against the registered model path."""

    if field_spec.name != path:
        msg = f"FieldSpec name {field_spec.name!r} must match field path {path!r}."
        raise InvalidResourceError(msg)
    if field_spec.relation_depth != relation_depth:
        msg = f"FieldSpec relation depth for {path!r} does not match the model path."
        raise InvalidResourceError(msg)
    return field_spec


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
    for path, config in fields.items():
        resolution = resolve_field_path(model, path)
        if isinstance(config, FieldSpec):
            field_specs[path] = validate_field_spec(
                path,
                config,
                resolution.relation_depth,
            )
            continue

        if not isinstance(config, Mapping):
            msg = f"Field config for {path!r} must be a mapping."
            raise InvalidResourceError(msg)

        field_config = dict(config)
        unknown_keys = set(field_config) - ALLOWED_FIELD_CONFIG_KEYS
        if unknown_keys:
            unknown_keys_display = ", ".join(sorted(unknown_keys))
            msg = f"Unknown field config keys for {path!r}: {unknown_keys_display}."
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
        label = str(
            field_config.get("label") or default_field_label(path, resolution.field)
        )
        field_type = str(field_config.get("type") or get_field_type(resolution.field))
        requires_permission = field_config.get("requires_permission")
        if requires_permission is not None and not isinstance(requires_permission, str):
            msg = f"requires_permission for {path!r} must be a string."
            raise InvalidResourceError(msg)

        field_specs[path] = FieldSpec(
            name=path,
            label=label,
            type=field_type,
            relation_depth=resolution.relation_depth,
            sensitive=sensitive,
            llm_visible=llm_visible,
            result_visible=result_visible,
            filter_only=get_bool_field_config(
                field_config,
                "filter_only",
                default=False,
            ),
            requires_permission=requires_permission,
            metric=get_bool_field_config(field_config, "metric", default=False),
        )

    return field_specs


def build_metric_specs(
    *, metrics: Sequence[Metric], fields: Mapping[str, FieldSpec]
) -> dict[str, Metric]:
    """Validate and normalize metric configuration."""

    metric_specs: dict[str, Metric] = {}
    for metric in metrics:
        if metric.name in metric_specs:
            msg = f"Duplicate metric name {metric.name!r}."
            raise InvalidMetricError(msg)
        if metric.field not in fields:
            msg = f"Metric {metric.name!r} references unknown field {metric.field!r}."
            raise UnknownFieldError(msg)
        metric_specs[metric.name] = metric
    return metric_specs


def default_field_label(path: str, field: models.Field) -> str:
    """Return a human-readable default label for a field path."""

    if "." not in path:
        return str(getattr(field, "verbose_name", path)).title()
    return path.replace(".", " ").replace("_", " ").title()
