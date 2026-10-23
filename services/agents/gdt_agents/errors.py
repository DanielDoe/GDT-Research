"""Errors that must reach the researcher instead of being replaced with data."""


class AgentError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, details: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class ProviderError(AgentError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        retryable: bool = False,
        status_code: int = 502,
    ):
        super().__init__(
            message,
            status_code=status_code,
            details={"provider": provider, "retryable": retryable},
        )
        self.provider = provider
        self.retryable = retryable


class JobCancelled(Exception):
    """Raised when a worker observes a cancellation request."""
