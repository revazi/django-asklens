"""Semantic resource registry."""

from collections.abc import Iterable, Mapping, Sequence

from django.db import models

from django_asklens.catalog.resources import (
    BaseQuerySetHook,
    CatalogSnapshot,
    FieldConfig,
    FieldSpec,
    Metric,
    SemanticResource,
    normalize_resource_name,
)
from django_asklens.exceptions import DuplicateResourceError, UnknownResourceError


class CatalogRegistry:
    """In-memory registry of explicitly configured semantic resources."""

    def __init__(self) -> None:
        self._resources: dict[str, SemanticResource] = {}

    def register(
        self,
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
        requires_permission: str | None = None,
    ) -> SemanticResource:
        """Register one semantic resource and return its normalized metadata."""

        resource = SemanticResource.build(
            model=model,
            fields=fields,
            name=name,
            label=label,
            description=description,
            synonyms=synonyms,
            default_date_field=default_date_field,
            metrics=metrics,
            base_queryset=base_queryset,
            requires_permission=requires_permission,
        )
        if resource.name in self._resources:
            msg = f"Semantic resource {resource.name!r} is already registered."
            raise DuplicateResourceError(msg)

        self._resources[resource.name] = resource
        return resource

    def get(self, name: str) -> SemanticResource:
        """Return a registered semantic resource by normalized name."""

        normalized_name = normalize_resource_name(name)
        try:
            return self._resources[normalized_name]
        except KeyError as exc:
            msg = f"Unknown semantic resource {name!r}."
            raise UnknownResourceError(msg) from exc

    def all(self) -> tuple[SemanticResource, ...]:
        """Return all registered semantic resources in registration order."""

        return tuple(self._resources.values())

    def clear(self) -> None:
        """Clear all resources from this registry."""

        self._resources.clear()

    def to_dict(
        self,
        *,
        include_sensitive: bool = False,
        include_hidden: bool = False,
        include_internal: bool = False,
        permissions: Iterable[str] | None = None,
    ) -> CatalogSnapshot:
        """Serialize the registry as catalog metadata."""

        permission_set = frozenset(permissions or ())
        return {
            "resources": [
                resource.to_dict(
                    include_sensitive=include_sensitive,
                    include_hidden=include_hidden,
                    include_internal=include_internal,
                    permissions=permission_set,
                )
                for resource in self._resources.values()
                if resource.is_catalog_visible(permissions=permission_set)
            ]
        }


default_registry = CatalogRegistry()


def register(
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
    requires_permission: str | None = None,
) -> SemanticResource:
    """Register one resource in the default AskLens catalog registry."""

    return default_registry.register(
        model=model,
        fields=fields,
        name=name,
        label=label,
        description=description,
        synonyms=synonyms,
        default_date_field=default_date_field,
        metrics=metrics,
        base_queryset=base_queryset,
        requires_permission=requires_permission,
    )


def get_resource(name: str) -> SemanticResource:
    """Return a resource from the default AskLens catalog registry."""

    return default_registry.get(name)


def serialize_catalog(
    *,
    include_sensitive: bool = False,
    include_hidden: bool = False,
    include_internal: bool = False,
    permissions: Iterable[str] | None = None,
) -> CatalogSnapshot:
    """Serialize the default AskLens catalog registry."""

    return default_registry.to_dict(
        include_sensitive=include_sensitive,
        include_hidden=include_hidden,
        include_internal=include_internal,
        permissions=permissions,
    )
