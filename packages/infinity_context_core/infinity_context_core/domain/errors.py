"""Typed domain and application errors for infinity_context_core."""


class MemoryError(Exception):
    """Base class for infinity context errors."""

    code = "memory.internal"
    retryable = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class MemoryValidationError(MemoryError):
    code = "memory.validation"


class MemoryPolicyBlockedError(MemoryError):
    code = "memory.policy_blocked"


class MemoryIngressLimitError(MemoryError):
    code = "memory.capture.ingress_limited"
    retryable = True


class MemoryQuotaExceededError(MemoryError):
    code = "memory.quota_exceeded"


class MemoryConflictError(MemoryError):
    code = "memory.conflict"


class MemoryNotFoundError(MemoryError):
    code = "memory.not_found"


class MemoryForbiddenError(MemoryError):
    code = "memory.forbidden"


class MemoryUnauthorizedError(MemoryError):
    code = "memory.unauthorized"


class MemoryInvariantError(MemoryError):
    code = "memory.invariant"


class MemoryInfrastructureError(MemoryError):
    code = "memory.infrastructure"
    retryable = True
