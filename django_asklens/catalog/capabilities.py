"""Permission-scoped query guidance built from the semantic catalog."""

import re
from collections.abc import Iterable, Sequence
from typing import Literal, NotRequired, TypedDict

from django_asklens.catalog.registry import serialize_catalog
from django_asklens.catalog.resources import (
    CatalogSnapshot,
    FieldCatalogItem,
    MetricCatalogItem,
    ResourceCatalogItem,
)

DATE_FIELD_TYPES = {"date", "datetime"}
MAX_RESOURCE_EXAMPLES = 3
SCOPED_PERMISSION_RE = re.compile(
    r"^(?P<kind>[A-Za-z][A-Za-z0-9_-]*):(?P<scope>[^:]+):(?P<permission>.+)$"
)

ScopeLevel = Literal["unknown", "single", "multiple", "all"]


class CapabilityField(TypedDict):
    """Field guidance for one visible catalog field."""

    name: str
    label: str
    type: str
    relation_depth: int
    can_filter: bool
    can_select: bool
    can_group: bool
    can_order: bool
    can_date_bucket: bool
    sensitive: NotRequired[bool]
    requires_permission: NotRequired[str]


class CapabilityMetric(TypedDict):
    """Metric guidance for one registered aggregate."""

    name: str
    label: str
    op: str
    field: str


class CapabilityScope(TypedDict):
    """Sanitized row-scope guidance for one visible resource."""

    level: ScopeLevel
    guidance: str
    kind: NotRequired[str]


class CapabilityResource(TypedDict):
    """Human-readable query guidance for one visible resource."""

    name: str
    label: str
    description: str
    synonyms: list[str]
    default_date_field: str | None
    fields: list[CapabilityField]
    metrics: list[CapabilityMetric]
    date_fields: list[CapabilityField]
    examples: list[str]
    guidance: list[str]
    scope: CapabilityScope
    requires_permission: NotRequired[str]


class CapabilitiesSnapshot(TypedDict):
    """Permission-scoped AskLens capabilities payload."""

    summary: str
    query_patterns: list[str]
    limitations: list[str]
    resources: list[CapabilityResource]
    examples: list[str]


def build_capabilities(
    *,
    permissions: Iterable[str] | None = None,
    catalog: CatalogSnapshot | None = None,
) -> CapabilitiesSnapshot:
    """Return safe, human-readable query guidance for visible catalog metadata.

    The payload is derived only from permission-scoped catalog metadata. It does
    not inspect database rows, sample values, credentials, environment values,
    or private model internals.
    """

    permission_set = frozenset(permissions or ())
    scoped_catalog = (
        catalog
        if catalog is not None
        else serialize_catalog(permissions=permission_set)
    )
    resources = [
        build_resource_capability(resource, permissions=permission_set)
        for resource in scoped_catalog.get("resources", [])
    ]
    examples = collect_examples(resources)
    return {
        "summary": build_summary(resources),
        "query_patterns": build_query_patterns(),
        "limitations": build_limitations(),
        "resources": resources,
        "examples": examples,
    }


def build_summary(resources: Sequence[CapabilityResource]) -> str:
    """Return a short top-level capabilities summary."""

    resource_count = len(resources)
    if resource_count == 0:
        return "No AskLens resources are queryable for this request."
    if resource_count == 1:
        return "You can ask read-only list and aggregate questions over 1 resource."
    return (
        "You can ask read-only list and aggregate questions over "
        f"{resource_count} resources."
    )


def build_query_patterns() -> list[str]:
    """Return supported natural-language query patterns."""

    return [
        "List records with exposed fields from one visible resource.",
        "Filter by exposed fields such as status, dates, booleans, or related labels.",
        "Group aggregate metrics by exposed fields.",
        (
            "Trend aggregate metrics by day, week, month, quarter, or year "
            "when a date field is exposed."
        ),
        (
            "Order results by selected fields or requested metrics, with "
            "configured row limits."
        ),
    ]


def build_limitations() -> list[str]:
    """Return safe usage limits for capabilities consumers."""

    return [
        (
            "AskLens only queries resources and fields listed in this "
            "capabilities response."
        ),
        (
            "AskLens executes validated read-only Django ORM queries; it does "
            "not execute raw SQL."
        ),
        "AskLens cannot create, update, or delete data.",
        (
            "Catalog and capabilities metadata do not include database rows or "
            "sample values."
        ),
        (
            "Tenant and row-level scope still depends on each resource base "
            "queryset for the current request."
        ),
    ]


def build_resource_capability(
    resource: ResourceCatalogItem,
    *,
    permissions: Iterable[str] = (),
) -> CapabilityResource:
    """Return guidance for one visible catalog resource."""

    scope = infer_capability_scope(
        required_permission=resource.get("requires_permission"),
        permissions=permissions,
    )
    fields = [build_field_capability(field) for field in resource.get("fields", [])]
    metrics = [
        build_metric_capability(metric) for metric in resource.get("metrics", [])
    ]
    date_fields = [field for field in fields if field["can_date_bucket"]]
    capability: CapabilityResource = {
        "name": resource["name"],
        "label": resource["label"],
        "description": resource.get("description", ""),
        "synonyms": resource.get("synonyms", []),
        "default_date_field": resource.get("default_date_field"),
        "fields": fields,
        "metrics": metrics,
        "date_fields": date_fields,
        "examples": build_resource_examples(
            resource,
            fields=fields,
            metrics=metrics,
            scope=scope,
        ),
        "guidance": build_resource_guidance(
            resource,
            fields=fields,
            metrics=metrics,
            scope=scope,
        ),
        "scope": scope,
    }
    if resource.get("requires_permission"):
        capability["requires_permission"] = resource["requires_permission"]
    return capability


def infer_capability_scope(
    *,
    required_permission: str | None,
    permissions: Iterable[str],
) -> CapabilityScope:
    """Infer sanitized scope metadata from permission tokens.

    AskLens treats permission strings as opaque for authorization, but it also
    recognizes common scoped tokens such as ``facility:123:ReportView`` to give
    LLMs safe guidance about whether examples may imply cross-scope access. The
    returned metadata never includes scope identifiers or tenant names.
    """

    if required_permission is None:
        return {
            "level": "unknown",
            "guidance": (
                "Use only rows visible through the resource base queryset; do "
                "not imply broader access than this request has."
            ),
        }

    permission_set = frozenset(permissions)
    if required_permission in permission_set:
        return {
            "level": "all",
            "guidance": (
                "This request has an unscoped permission token for this "
                "resource; the resource base queryset still controls rows."
            ),
        }

    scoped_values: dict[str, set[str]] = {}
    wildcard_kinds: set[str] = set()
    for permission in permission_set:
        match = SCOPED_PERMISSION_RE.match(permission)
        if match is None or match.group("permission") != required_permission:
            continue
        kind = match.group("kind")
        scope_value = match.group("scope")
        if scope_value == "*":
            wildcard_kinds.add(kind)
        else:
            scoped_values.setdefault(kind, set()).add(scope_value)

    if wildcard_kinds:
        kind = sorted(wildcard_kinds)[0]
        return {
            "level": "all",
            "kind": kind,
            "guidance": (
                f"This request may query all visible {pluralize_scope_kind(kind)} "
                "for this resource, subject to the resource base queryset."
            ),
        }

    scope_count = sum(len(values) for values in scoped_values.values())
    if scope_count == 1:
        kind = next(iter(scoped_values))
        return {
            "level": "single",
            "kind": kind,
            "guidance": (
                f"Visible rows are scoped to one {humanize_scope_kind(kind)}. "
                f"Do not suggest comparing, grouping, or filtering across "
                f"{pluralize_scope_kind(kind)}."
            ),
        }
    if scope_count > 1:
        kind = sorted(scoped_values)[0]
        return {
            "level": "multiple",
            "kind": kind,
            "guidance": (
                f"Visible rows may span multiple {pluralize_scope_kind(kind)}. "
                "Cross-scope examples are allowed only when the required "
                "fields are exposed in this capabilities payload."
            ),
        }

    return {
        "level": "unknown",
        "guidance": (
            "Use only rows visible through the resource base queryset; do not "
            "imply broader access than this request has."
        ),
    }


def humanize_scope_kind(kind: str) -> str:
    """Return a readable scope-kind label."""

    return kind.replace("_", " ").replace("-", " ")


def pluralize_scope_kind(kind: str) -> str:
    """Return a conservative plural label for a scope kind."""

    label = humanize_scope_kind(kind)
    if label.endswith("y") and len(label) > 1 and label[-2] not in "aeiou":
        return f"{label[:-1]}ies"
    if label.endswith("s"):
        return label
    return f"{label}s"


def build_field_capability(field: FieldCatalogItem) -> CapabilityField:
    """Return usage guidance for one field."""

    is_filter_only = field.get("filter_only", False)
    is_result_visible = field.get("result_visible", True)
    can_use_in_results = not is_filter_only and is_result_visible
    capability: CapabilityField = {
        "name": field["name"],
        "label": field["label"],
        "type": field["type"],
        "relation_depth": field["relation_depth"],
        "can_filter": True,
        "can_select": can_use_in_results,
        "can_group": can_use_in_results,
        "can_order": can_use_in_results,
        "can_date_bucket": can_use_in_results and field["type"] in DATE_FIELD_TYPES,
    }
    if field.get("sensitive"):
        capability["sensitive"] = True
    if field.get("requires_permission"):
        capability["requires_permission"] = field["requires_permission"]
    return capability


def build_metric_capability(metric: MetricCatalogItem) -> CapabilityMetric:
    """Return usage guidance for one metric."""

    return {
        "name": metric["name"],
        "label": metric["label"],
        "op": metric["op"],
        "field": metric["field"],
    }


def build_resource_guidance(
    resource: ResourceCatalogItem,
    *,
    fields: Sequence[CapabilityField],
    metrics: Sequence[CapabilityMetric],
    scope: CapabilityScope,
) -> list[str]:
    """Return short natural-language guidance for one resource."""

    guidance = [f"Use resource `{resource['name']}` for {resource['label']} questions."]
    selectable_count = len([field for field in fields if field["can_select"]])
    if selectable_count:
        guidance.append(f"You can list {selectable_count} exposed fields.")
    if metrics:
        guidance.append(f"You can request {len(metrics)} registered aggregate metrics.")
    if any(field["can_date_bucket"] for field in fields):
        guidance.append(
            "You can ask for date trends by day, week, month, quarter, or year."
        )
    guidance.append(scope["guidance"])
    return guidance


def build_resource_examples(
    resource: ResourceCatalogItem,
    *,
    fields: Sequence[CapabilityField],
    metrics: Sequence[CapabilityMetric],
    scope: CapabilityScope,
) -> list[str]:
    """Return deterministic example questions for one resource."""

    examples: list[str] = []
    if is_single_scope_resource(resource, scope=scope):
        return examples

    selectable_fields = filter_single_scope_dimension_fields(
        [field for field in fields if field["can_select"]],
        scope=scope,
    )
    group_fields = sorted(
        [field for field in selectable_fields if not field["can_date_bucket"]],
        key=group_field_example_sort_key,
    )
    date_fields = [field for field in selectable_fields if field["can_date_bucket"]]

    if selectable_fields:
        examples.append(build_list_example(resource, selectable_fields))
    if metrics and group_fields:
        examples.append(
            build_metric_by_field_example(resource, metrics[0], group_fields[0])
        )
    if metrics and date_fields:
        examples.append(build_metric_trend_example(metrics[0], date_fields[0]))

    return dedupe_preserve_order(examples)[:MAX_RESOURCE_EXAMPLES]


def is_single_scope_resource(
    resource: ResourceCatalogItem | CapabilityResource,
    *,
    scope: CapabilityScope,
) -> bool:
    """Return whether a resource represents the one visible scope itself."""

    if scope["level"] != "single" or "kind" not in scope:
        return False
    kind = humanize_scope_kind(scope["kind"]).lower()
    plural = pluralize_scope_kind(scope["kind"]).lower()
    candidates = {
        str(resource["name"]).replace("_", " ").replace("-", " ").lower(),
        str(resource["label"]).lower(),
    }
    candidates.update(synonym.lower() for synonym in resource.get("synonyms", []))
    return kind in candidates or plural in candidates


def filter_single_scope_dimension_fields(
    fields: Sequence[CapabilityField],
    *,
    scope: CapabilityScope,
) -> list[CapabilityField]:
    """Remove single-scope dimensions from examples.

    If a request is scoped to one facility/account/etc., examples like "by
    facility" imply comparisons the user cannot make. Query execution remains
    safe either way; this only improves help UX and provider guidance.
    """

    if scope["level"] != "single" or "kind" not in scope:
        return list(fields)
    kind = scope["kind"]
    return [
        field
        for field in fields
        if not is_scope_dimension_field(
            field_name=field["name"],
            field_label=field["label"],
            scope_kind=kind,
        )
    ]


def is_scope_dimension_field(
    *,
    field_name: str,
    field_label: str,
    scope_kind: str,
) -> bool:
    """Return whether a field appears to identify the scoped dimension."""

    normalized_kind = humanize_scope_kind(scope_kind).lower()
    normalized_plural = pluralize_scope_kind(scope_kind).lower()
    lower_name = field_name.lower()
    lower_label = field_label.lower()
    label_tokens = set(re.findall(r"[a-z0-9]+", lower_label))
    return (
        lower_name == scope_kind.lower()
        or lower_name == f"{scope_kind.lower()}_id"
        or lower_name.startswith(f"{scope_kind.lower()}.")
        or normalized_kind in label_tokens
        or normalized_plural in label_tokens
    )


def group_field_example_sort_key(field: CapabilityField) -> tuple[int, int, str]:
    """Sort fields so generated examples prefer readable dimensions over IDs."""

    lower_name = field["name"].lower()
    lower_label = field["label"].lower()
    is_identifier = (
        lower_name == "id" or lower_name.endswith("_id") or " id" in lower_label
    )
    return (1 if is_identifier else 0, field["relation_depth"], field["name"])


def build_list_example(
    resource: ResourceCatalogItem,
    fields: Sequence[CapabilityField],
) -> str:
    """Return a list-style example question."""

    labels = join_labels([field["label"] for field in fields[:3]])
    return f"List {resource['label']} with {labels}"


def build_metric_by_field_example(
    resource: ResourceCatalogItem,
    metric: CapabilityMetric,
    field: CapabilityField,
) -> str:
    """Return an aggregate-by-field example question."""

    metric_phrase = metric_label_for_question(resource, metric)
    return f"Show {metric_phrase} by {field['label']}"


def build_metric_trend_example(
    metric: CapabilityMetric,
    field: CapabilityField,
) -> str:
    """Return an aggregate trend example question."""

    return f"Trend {metric['label']} by month using {field['label']}"


def metric_label_for_question(
    resource: ResourceCatalogItem,
    metric: CapabilityMetric,
) -> str:
    """Return a readable metric phrase for generated examples."""

    if metric["op"] == "count":
        return f"count of {resource['label']}"
    return metric["label"]


def join_labels(labels: Sequence[str]) -> str:
    """Join field labels for display in a short example."""

    if not labels:
        return "exposed fields"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def collect_examples(resources: Sequence[CapabilityResource]) -> list[str]:
    """Collect global examples from resource examples."""

    return dedupe_preserve_order(
        example for resource in resources for example in resource["examples"]
    )


def dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    """Return values without duplicates while preserving order."""

    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
