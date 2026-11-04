"""
Custom exception hierarchy for MuleCatch.
All business-logic errors inherit from MuleCatchError.
"""


class MuleCatchError(Exception):
    """Base exception for all MuleCatch domain errors."""

    def __init__(self, message: str = "An error occurred", details: str = ""):
        self.message = message
        self.details = details
        super().__init__(self.message)


class NotFoundError(MuleCatchError):
    """Resource not found (404)."""

    def __init__(self, resource: str, resource_id: str):
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            details=f"resource={resource}, id={resource_id}",
        )


class AuthenticationError(MuleCatchError):
    """Authentication failure (401)."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message)


class AuthorizationError(MuleCatchError):
    """Authorization failure (403)."""

    def __init__(self, message: str = "Not authorized"):
        super().__init__(message=message)


class ValidationError(MuleCatchError):
    """Input validation error (400)."""

    def __init__(self, message: str = "Validation error", details: str = ""):
        super().__init__(message=message, details=details)


class ConflictError(MuleCatchError):
    """Conflict with current state (409)."""

    def __init__(self, message: str = "Conflict", details: str = ""):
        super().__init__(message=message, details=details)


class ServiceUnavailableError(MuleCatchError):
    """External service unavailable (503)."""

    def __init__(self, message: str = "Service unavailable", details: str = ""):
        super().__init__(message=message, details=details)
