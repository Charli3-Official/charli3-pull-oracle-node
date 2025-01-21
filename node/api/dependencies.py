"""Dependency injection module."""

from typing import Optional

from core.errors import NodeNotInitializedError
from core.odv import OdvService

_odv_service: Optional[OdvService] = None


async def initialize_odv_service(**kwargs) -> None:
    """Initialize the ODV service singleton."""
    global _odv_service
    _odv_service = OdvService(**kwargs)


async def get_odv_service() -> OdvService:
    """Dependency provider for ODV service.

    Returns:
        OdvService: Initialized ODV service instance

    Raises:
        NodeNotInitializedError: If service not initialized
    """
    if _odv_service is None:
        raise NodeNotInitializedError()
    return _odv_service
