"""Error definitions for the ODV node service."""

from fastapi import HTTPException, status


class NodeError(HTTPException):
    """Base error for API-level operations."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class NodeNotInitializedError(NodeError):
    """Service not initialized error."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ODV service not initialized",
        )


# Service Level Errors
class NodeServiceError(Exception):
    """Base exception for service operations."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __str__(self) -> str:
        return self.__doc__ or "Service operation failed"


class ValidationError(NodeServiceError):
    """Base validation error."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str):
        self.message = message

    def __str__(self) -> str:
        return self.message


class NodeNotRegisteredError(ValidationError):
    """Node is not registered for oracle."""

    status_code = status.HTTP_403_FORBIDDEN


class OraclePausedError(ValidationError):
    """Oracle is currently paused."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class TimestampValidationError(ValidationError):
    """Timestamp is outside validity interval."""

    status_code = status.HTTP_400_BAD_REQUEST


class RateAggregationError(NodeServiceError):
    """Rate aggregation failed."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class MessageError(NodeServiceError):
    """Base message handling error."""

    status_code = status.HTTP_400_BAD_REQUEST


class MessageCreationError(MessageError):
    """Failed to create message."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class MessageSigningError(MessageError):
    """Failed to sign message."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class TransactionSigningError(MessageError):
    """Failed to sign transaction."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class InvalidNodeSignatureError(ValidationError):
    """Error when a node's signature is invalid during validation."""

    status_code = status.HTTP_400_BAD_REQUEST
