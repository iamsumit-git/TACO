"""
app/exceptions.py — Custom exceptions for TACO pipeline.
"""


class BudgetExceededException(Exception):
    """Raised when a user/org spend exceeds their configured budget limit."""

    def __init__(self, spent_usd: float, limit_usd: float, entity_id: str):
        self.spent_usd = spent_usd
        self.limit_usd = limit_usd
        self.entity_id = entity_id
        super().__init__(
            f"Budget exceeded for {entity_id}: spent ${spent_usd:.6f}, limit ${limit_usd:.4f}"
        )


class ContextTooLargeException(Exception):
    """Raised when estimated tokens exceed the model's context window."""

    def __init__(self, estimated_tokens: int, context_window: int, model: str):
        self.estimated_tokens = estimated_tokens
        self.context_window = context_window
        self.model = model
        super().__init__(
            f"Token estimate {estimated_tokens} exceeds context window {context_window} for model {model}"
        )


class NoModelAvailableException(Exception):
    """Raised when no active model is available for the requested tier."""

    def __init__(self, tier: str):
        self.tier = tier
        super().__init__(f"No active model available for tier: {tier}")


class ProviderErrorException(Exception):
    """Raised when an LLM provider returns an error response."""

    def __init__(self, provider: str, status_code: int, message: str):
        self.provider = provider
        self.status_code = status_code
        self.message = message
        super().__init__(f"Provider {provider} returned {status_code}: {message}")


class ProviderRateLimitException(ProviderErrorException):
    """Raised when a provider returns 429 Too Many Requests."""

    def __init__(self, provider: str):
        super().__init__(provider, 429, "Rate limit exceeded")
