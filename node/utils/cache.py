"""Caching utility with TTL"""

import asyncio
import logging
import time
from typing import Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ResponseCache(Generic[T]):
    """An asynchronous in-memory cache with time-based expiration (TTL)."""

    def __init__(self, ttl: int = 60):
        """Initialize the cache with a time-to-live in seconds."""
        self.ttl = ttl
        self._cache: dict[str, tuple[T, float]] = {}  # {key: (value, timestamp)}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        """Get item from cache if it exists and is valid."""
        async with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self.ttl:
                    logger.debug(
                        f"Cache hit for key '{key}' (age: {time.time() - timestamp:.2f}s)"
                    )
                    return value
                else:
                    logger.debug(f"Cache expired for key '{key}'")
                    del self._cache[key]
            else:
                logger.debug(f"Cache miss for key '{key}'")
        return None

    async def set(self, key: str, value: T) -> None:
        """Store item in cache with current timestamp."""
        async with self._lock:
            self._cache[key] = (value, time.time())
            logger.debug(f"Cache updated for key '{key}'")

    async def clear(self, key: Optional[str] = None) -> None:
        """Clear cache entry or all entries if key is None."""
        async with self._lock:
            if key is None:
                self._cache.clear()
                logger.debug("Cache cleared completely")
            elif key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache entry cleared for '{key}'")

    async def get_or_update(self, key: str, fetch_func) -> T:
        """Get from cache or update if invalid."""
        value = await self.get(key)

        # If not in cache or expired, fetch and update
        if value is None:
            logger.info(f"Fetching fresh data for '{key}'")
            value = await fetch_func()
            await self.set(key, value)

        return value
