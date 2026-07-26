"""Django model introspection helpers for semantic resources."""

from dataclasses import dataclass

from django.core.exceptions import FieldDoesNotExist
from django.db import models

from django_asklens.exceptions import UnknownFieldError


@dataclass(frozen=True, slots=True)
class FieldResolution:
    """Resolved metadata for a private Django model field binding."""

    path: str
    field: models.Field
    relation_depth: int
    relationship_edges: tuple[str, ...]
    nullable: bool


def resolve_field_path(model: type[models.Model], path: str) -> FieldResolution:
    """Resolve a private ``__``-separated binding against a Django model."""

    parts = path.split("__")
    if not path or any(part == "" for part in parts):
        msg = f"Invalid empty field binding for {model._meta.label}: {path!r}."
        raise UnknownFieldError(msg)

    current_model = model
    relationship_edges: list[str] = []
    relationship_nullable = False

    for index, part in enumerate(parts):
        try:
            field = current_model._meta.get_field(part)
        except FieldDoesNotExist as exc:
            msg = f"Unknown field binding for {model._meta.label}: {path!r}."
            raise UnknownFieldError(msg) from exc

        is_last_part = index == len(parts) - 1
        if is_last_part:
            return FieldResolution(
                path=path,
                field=field,
                relation_depth=len(relationship_edges),
                relationship_edges=tuple(relationship_edges),
                nullable=relationship_nullable or bool(field.null),
            )

        related_model = getattr(field, "related_model", None)
        if not field.is_relation or related_model is None:
            traversed_path = "__".join(parts[: index + 1])
            msg = (
                f"Cannot traverse non-relation field binding {traversed_path!r} "
                f"while resolving {path!r} for {model._meta.label}."
            )
            raise UnknownFieldError(msg)

        relationship_edges.append("__".join(parts[: index + 1]))
        relationship_nullable = relationship_nullable or any(
            (
                bool(field.null),
                bool(field.one_to_many),
                bool(field.many_to_many),
            )
        )
        current_model = related_model

    msg = f"Unknown field binding for {model._meta.label}: {path!r}."
    raise UnknownFieldError(msg)


def get_field_type(field: models.Field) -> str:
    """Return a stable, broad type label for catalog serialization."""

    if isinstance(field, models.BooleanField):
        return "boolean"
    if isinstance(field, (models.DateTimeField,)):
        return "datetime"
    if isinstance(field, (models.DateField,)):
        return "date"
    if isinstance(field, (models.TimeField,)):
        return "time"
    if isinstance(field, (models.IntegerField, models.AutoField, models.BigAutoField)):
        return "integer"
    if isinstance(field, models.DecimalField):
        return "decimal"
    if isinstance(field, models.FloatField):
        return "float"
    if isinstance(field, models.UUIDField):
        return "uuid"
    if isinstance(
        field,
        (
            models.CharField,
            models.EmailField,
            models.SlugField,
            models.TextField,
            models.URLField,
        ),
    ):
        return "string"
    if field.is_relation:
        return "relation"

    return field.get_internal_type().lower()
