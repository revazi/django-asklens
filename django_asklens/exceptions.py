"""Typed exceptions raised by Django AskLens."""


class AskLensError(Exception):
    """Base exception for Django AskLens errors."""


class CatalogError(AskLensError):
    """Base exception for semantic catalog errors."""


class DuplicateResourceError(CatalogError):
    """Raised when a semantic resource name is already registered."""


class UnknownResourceError(CatalogError):
    """Raised when a semantic resource cannot be found."""


class UnknownFieldError(CatalogError):
    """Raised when a configured field path is not valid for a model."""


class InvalidResourceError(CatalogError):
    """Raised when a semantic resource configuration is invalid."""


class InvalidMetricError(CatalogError):
    """Raised when a metric configuration is invalid."""


class PlanValidationError(AskLensError):
    """Raised when a QueryPlan is malformed or unsafe."""


class UnknownMetricError(PlanValidationError):
    """Raised when a QueryPlan references an unknown metric."""


class PermissionDeniedError(AskLensError):
    """Raised when a QueryPlan attempts to access disallowed metadata."""


class UnsupportedQueryError(PlanValidationError):
    """Raised when a QueryPlan asks for unsupported behavior."""


class LLMProviderError(AskLensError):
    """Raised when an LLM provider cannot return a usable response."""


class ResultSerializationError(AskLensError):
    """Raised when result data cannot be serialized safely."""


class VisualizationHintError(ResultSerializationError):
    """Raised when visualization hint metadata is invalid."""
