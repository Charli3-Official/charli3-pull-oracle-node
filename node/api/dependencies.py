"""Dependency injection module."""

from typing import Optional

from node.core.errors import NodeNotInitializedError
from node.core.odv import OdvService

_odv_service: Optional[OdvService] = None


async def initialize_odv_service(**kwargs) -> OdvService:
    """Initialize the ODV service singleton."""
    global _odv_service
    _odv_service = OdvService(**kwargs)
    return _odv_service


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
