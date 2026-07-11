"""Prompt-size optimization helpers for provider calls."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from django_asklens.catalog.capabilities import CapabilitiesSnapshot

TOKEN_RE = re.compile(r"[a-z0-9]+")
DEFAULT_SHORTLIST_LIMIT = 4


def build_provider_prompt_capabilities(
    *,
    question: str,
    capabilities: CapabilitiesSnapshot,
    full_capabilities: bool = False,
    max_resources: int = DEFAULT_SHORTLIST_LIMIT,
) -> dict[str, Any]:
    """Return compact permission-scoped capabilities for provider prompts.

    This function never expands visibility. It only copies from an already
    permission-scoped capabilities payload and may narrow resources for likely
    data questions. Explicit help/capability prompts should set
    ``full_capabilities=True`` so users can ask what is available across the
    whole visible catalog.
    """

    if full_capabilities:
        return dict(capabilities)

    resources = list(capabilities.get("resources", []))
    if max_resources > 0:
        resources = shortlist_capability_resources(
            question=question,
            resources=resources,
            max_resources=max_resources,
        )

    compact_resources = [
        compact_capability_resource(resource) for resource in resources
    ]
    return {
        "summary": capabilities.get("summary", ""),
        "resources": compact_resources,
    }


def shortlist_capability_resources(
    *,
    question: str,
    resources: Sequence[Mapping[str, Any]],
    max_resources: int = DEFAULT_SHORTLIST_LIMIT,
) -> list[Mapping[str, Any]]:
    """Return likely resources for a question without adding new visibility.

    The shortlist is a best-effort prompt-size optimization, not an
    authorization decision. Query validation still runs against the normal
    catalog and request permissions after provider output is returned.
    """

    if max_resources <= 0 or len(resources) <= max_resources:
        return list(resources)

    question_tokens = tokenize_prompt_text(question)
    if not question_tokens:
        return list(resources[:max_resources])

    scored = [
        (score_resource_for_question(resource, question_tokens), index, resource)
        for index, resource in enumerate(resources)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [resource for score, _, resource in scored if score > 0]
    if not selected:
        return list(resources[:max_resources])
    return selected[:max_resources]


def score_resource_for_question(
    resource: Mapping[str, Any],
    question_tokens: set[str],
) -> int:
    """Return a lexical relevance score for one visible resource."""

    score = 0
    score += 5 * len(question_tokens & resource_identity_tokens(resource))
    score += 3 * len(question_tokens & metric_tokens(resource))
    score += 2 * len(question_tokens & field_tokens(resource))
    return score


def compact_capability_resource(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Return the prompt-facing subset of one capability resource."""

    compact: dict[str, Any] = {
        "name": resource.get("name"),
        "label": resource.get("label"),
        "description": resource.get("description", ""),
        "synonyms": resource.get("synonyms", []),
        "default_date_field": resource.get("default_date_field"),
        "scope": resource.get("scope", {}),
        "fields": [
            compact_capability_field(field)
            for field in resource.get("fields", [])
            if isinstance(field, Mapping)
        ],
        "metrics": [
            compact_capability_metric(metric)
            for metric in resource.get("metrics", [])
            if isinstance(metric, Mapping)
        ],
    }
    if resource.get("scope_resource"):
        compact["scope_resource"] = True
    if resource.get("examples_enabled") is False:
        compact["examples_enabled"] = False
    return compact


def compact_capability_field(field: Mapping[str, Any]) -> dict[str, Any]:
    """Return provider-relevant field metadata without duplicated structures."""

    compact = {
        "name": field.get("name"),
        "label": field.get("label"),
        "type": field.get("type"),
        "can_filter": field.get("can_filter"),
        "can_select": field.get("can_select"),
        "can_group": field.get("can_group"),
        "can_order": field.get("can_order"),
        "can_date_bucket": field.get("can_date_bucket"),
    }
    if field.get("scope_dimension"):
        compact["scope_dimension"] = True
    if field.get("requires_permission"):
        compact["requires_permission"] = field.get("requires_permission")
    return compact


def compact_capability_metric(metric: Mapping[str, Any]) -> dict[str, Any]:
    """Return provider-relevant metric metadata."""

    return {
        "name": metric.get("name"),
        "label": metric.get("label"),
        "op": metric.get("op"),
        "field": metric.get("field"),
    }


def resource_identity_tokens(resource: Mapping[str, Any]) -> set[str]:
    """Return tokens describing a resource itself."""

    tokens = set()
    for key in ("name", "label", "description"):
        value = resource.get(key)
        if isinstance(value, str):
            tokens.update(tokenize_prompt_text(value))
    for synonym in resource.get("synonyms", []):
        if isinstance(synonym, str):
            tokens.update(tokenize_prompt_text(synonym))
    return tokens


def field_tokens(resource: Mapping[str, Any]) -> set[str]:
    """Return tokens for visible fields on a resource."""

    tokens = set()
    for field in resource.get("fields", []):
        if not isinstance(field, Mapping):
            continue
        for key in ("name", "label"):
            value = field.get(key)
            if isinstance(value, str):
                tokens.update(tokenize_prompt_text(value))
    return tokens


def metric_tokens(resource: Mapping[str, Any]) -> set[str]:
    """Return tokens for visible metrics on a resource."""

    tokens = set()
    for metric in resource.get("metrics", []):
        if not isinstance(metric, Mapping):
            continue
        for key in ("name", "label", "field"):
            value = metric.get(key)
            if isinstance(value, str):
                tokens.update(tokenize_prompt_text(value))
    return tokens


def tokenize_prompt_text(value: str) -> set[str]:
    """Tokenize names, labels, and questions for lightweight matching."""

    return set(TOKEN_RE.findall(value.replace("_", " ").replace(".", " ").lower()))


def estimate_prompt_tokens(text: str) -> int:
    """Return a deterministic rough token estimate for prompt measurements."""

    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)
