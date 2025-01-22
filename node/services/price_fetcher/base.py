"""Base adapter for rate providers."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class Rate:
    """Standard rate response across all adapters."""

    source: str
    price: float
    metadata: dict[str, Any]
    timestamp: float


class BaseAdapter(ABC):
    """Base adapter for fetching asset rates."""

    def __init__(
        self,
        base_asset: str,
        quote_asset: str,
        sources: list[Union[str, dict[str, Any]]],
        require_quote: bool = False,
        quote_method: Optional[str] = None,
    ) -> None:
        """Initialize base adapter.

        Args:
            base_asset: Base asset symbol/identifier
            quote_asset: Quote asset symbol/identifier
            sources: list of rate sources
            require_quote: Whether quote conversion is needed
            quote_method: Quote calculation method ('multiply' or 'divide'). Defaults to 'multiply'
        """
        self.base_asset = base_asset
        self.quote_asset = quote_asset
        self.sources = sources
        self.require_quote = require_quote
        self.quote_method = quote_method if quote_method else "multiply"

        if self.quote_method not in ["multiply", "divide"]:
            raise ValueError("quote_method must be 'multiply' or 'divide'")

    @abstractmethod
    async def get_rates(self) -> list[Rate]:
        """Fetch rates from configured sources.

        Returns:
            list of Rate objects with price data
        """
        pass

    def apply_quote(self, price: float, quote_rate: float) -> float:
        """Apply quote conversion to price if required.

        Args:
            price: Original price
            quote_rate: Quote currency rate

        Returns:
            Converted price
        """
        if not self.require_quote or quote_rate <= 0:
            return price

        return (
            price * quote_rate
            if self.quote_method == "multiply"
            else price / quote_rate
        )

    def log_config(self) -> None:
        """Log adapter configuration."""
        logger.info("=" * 40)
        logger.info(f"Adapter: {self.__class__.__name__}")
        logger.info(f"Pair: {self.base_asset}/{self.quote_asset}")
        logger.info(f"Sources: {len(self.sources)}")
        logger.info(f"Quote Required: {self.require_quote}")
        if self.require_quote:
            logger.info(f"Quote Method: {self.quote_method}")
        logger.info("=" * 40)
