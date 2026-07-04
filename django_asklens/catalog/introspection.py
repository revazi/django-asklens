"""Django model introspection helpers for semantic resources."""

from dataclasses import dataclass

from django.core.exceptions import FieldDoesNotExist
from django.db import models

from django_asklens.exceptions import UnknownFieldError


@dataclass(frozen=True, slots=True)
class FieldResolution:
    """Resolved metadata for a Django model field path."""

    path: str
    field: models.Field
    relation_depth: int


def resolve_field_path(model: type[models.Model], path: str) -> FieldResolution:
    """Resolve a dot-separated field path against a Django model."""

    parts = path.split(".")
    if not path or any(part == "" for part in parts):
        msg = f"Invalid empty field path for {model._meta.label}: {path!r}."
        raise UnknownFieldError(msg)

    current_model = model
    relation_depth = 0

    for index, part in enumerate(parts):
        try:
            field = current_model._meta.get_field(part)
        except FieldDoesNotExist as exc:
            msg = f"Unknown field path for {model._meta.label}: {path!r}."
            raise UnknownFieldError(msg) from exc

        is_last_part = index == len(parts) - 1
        if is_last_part:
            return FieldResolution(
                path=path,
                field=field,
                relation_depth=relation_depth,
            )

        related_model = getattr(field, "related_model", None)
        if not field.is_relation or related_model is None:
            traversed_path = ".".join(parts[: index + 1])
            msg = (
                f"Cannot traverse non-relation field {traversed_path!r} "
                f"while resolving {path!r} for {model._meta.label}."
            )
            raise UnknownFieldError(msg)

        relation_depth += 1
        current_model = related_model

    msg = f"Unknown field path for {model._meta.label}: {path!r}."
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
    if isinstance(field, (models.DecimalField, models.FloatField)):
        return "number"
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
