"""Private strict-wire adaptation, separate from AskLens application schemas.

OpenAI requires every object property to be required. For an originally optional,
non-nullable property, null on the wire means omission in the application. Null
already allowed by the original schema remains a value, not an omission marker.
This is not a general JSON Schema compiler or an output validator.
"""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from django_asklens.exceptions import LLMProviderError


def strict_wire_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a closed application schema into the provider's required/null form.

    Open maps cannot be closed without losing values, so reject them before I/O
    rather than silently changing their contract. Keep local references intact.
    """

    def adapt(node: Mapping[str, Any]) -> dict[str, Any]:
        result = deepcopy(dict(node))
        # Pydantic defaults are application behavior, not supported wire keywords.
        result.pop("default", None)
        if "$defs" in node:
            result["$defs"] = {
                name: adapt(value) for name, value in node["$defs"].items()
            }
        if "anyOf" in node:
            result["anyOf"] = [adapt(value) for value in node["anyOf"]]
        if isinstance(node.get("items"), Mapping):
            result["items"] = adapt(node["items"])
        if "properties" in node or _has_type(node, "object"):
            if node.get("additionalProperties") is not False:
                raise LLMProviderError("LLM strict schema requires closed objects.")
            properties = node.get("properties", {})
            required = node.get("required", ())
            result["properties"] = {}
            for name, value in properties.items():
                adapted = adapt(value)
                if name not in required and not _allows_null(value, schema):
                    adapted = {"anyOf": [adapted, {"type": "null"}]}
                result["properties"][name] = adapted
            result["required"] = list(properties)
        return result

    return adapt(schema)


def normalize_wire_response(
    payload: Mapping[str, Any], schema: Mapping[str, Any]
) -> dict[str, Any]:
    """Remove only added null omission markers, retaining invalid/unknown values.

    Existing application parsers and execution validation remain authoritative.
    No default values, coercions, branch cleanup or unknown-key filtering occur.
    """

    def normalize(value: Any, node: Mapping[str, Any]) -> Any:
        if "$ref" in node:
            return normalize(value, _resolve_ref(node["$ref"], schema))
        if "anyOf" in node:
            candidates = [
                normalize(value, branch)
                for branch in node["anyOf"]
                if _matches_shape(value, branch, schema)
            ]
            if candidates:
                # Never choose a lossy interpretation of an ambiguous union.
                if any(candidate != candidates[0] for candidate in candidates[1:]):
                    raise LLMProviderError(
                        "LLM strict response has ambiguous normalization."
                    )
                return candidates[0]
        if isinstance(value, Mapping) and "properties" in node:
            properties = node["properties"]
            required = node.get("required", ())
            result = {}
            for name, item in value.items():
                child = properties.get(name)
                if child is None:
                    result[name] = item
                elif not (
                    item is None
                    and name not in required
                    and not _allows_null(child, schema)
                ):
                    result[name] = normalize(item, child)
            return result
        if isinstance(value, list) and isinstance(node.get("items"), Mapping):
            return [normalize(item, node["items"]) for item in value]
        return value

    return normalize(payload, schema)


def _has_type(schema: Mapping[str, Any], name: str) -> bool:
    declared = schema.get("type")
    return declared == name or isinstance(declared, list) and name in declared


def _resolve_ref(ref: str, root: Mapping[str, Any]) -> Mapping[str, Any]:
    if not ref.startswith("#/"):
        raise LLMProviderError("LLM strict schema requires local references.")
    node = root
    try:
        for token in ref[2:].split("/"):
            node = node[token.replace("~1", "/").replace("~0", "~")]
    except (KeyError, TypeError) as exc:
        raise LLMProviderError("LLM strict schema reference is invalid.") from exc
    return node


def _allows_null(node: Mapping[str, Any], root: Mapping[str, Any]) -> bool:
    if "$ref" in node:
        return _allows_null(_resolve_ref(node["$ref"], root), root)
    if "anyOf" in node:
        return any(_allows_null(branch, root) for branch in node["anyOf"])
    if "enum" in node:
        return None in node["enum"]
    if "const" in node:
        return node["const"] is None
    return "type" not in node or _has_type(node, "null")


def _matches_shape(
    value: Any, node: Mapping[str, Any], root: Mapping[str, Any]
) -> bool:
    """Select structural union branches only; never validate or coerce output."""

    if "$ref" in node:
        return _matches_shape(value, _resolve_ref(node["$ref"], root), root)
    if "anyOf" in node:
        return any(_matches_shape(value, branch, root) for branch in node["anyOf"])
    if "type" not in node:
        return True
    if value is None:
        return _has_type(node, "null")
    if isinstance(value, Mapping):
        return _has_type(node, "object")
    if isinstance(value, list):
        return _has_type(node, "array")
    if isinstance(value, bool):
        return _has_type(node, "boolean")
    if isinstance(value, str):
        return _has_type(node, "string")
    return _has_type(node, "integer") or _has_type(node, "number")
