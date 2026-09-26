"""Shared exceptions for the local prompt evaluation package."""


class OllamaUnavailable(RuntimeError):
    """Raised when the local Ollama service or selected model is unavailable."""


class RetryableOllamaError(OllamaUnavailable):
    """A transient transport failure eligible for bounded retry/resume."""
