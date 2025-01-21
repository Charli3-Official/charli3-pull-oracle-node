"""CCXT adapter for centralized exchange rates."""

import asyncio
import logging
import time
from typing import Optional, Union

import ccxt.async_support as ccxt
from config.models import SourceConfig

from .base import BaseAdapter, Rate

logger = logging.getLogger(__name__)


class CCXTAdapter(BaseAdapter):
    """Adapter for fetching rates using CCXT."""

    def __init__(
        self,
        base_asset: str,
        quote_asset: str,
        sources: list[Union[str, SourceConfig]],
        require_quote: bool = False,
        quote_method: str = "multiply",
        concurrent_requests: int = 40,
    ):
        """Initialize CCXT adapter.

        Args:
            base_asset: Base asset symbol
            quote_asset: Quote asset symbol
            sources: list of exchange configs with 'name' and optional credentials
            require_quote: Whether quote conversion is needed
            quote_method: Quote calculation method
            concurrent_requests: Max concurrent exchange requests
        """
        super().__init__(base_asset, quote_asset, sources, require_quote, quote_method)
        self._exchanges: dict[str, ccxt.Exchange] = {}
        self._semaphore = asyncio.Semaphore(concurrent_requests)
        self._setup_exchanges()

    def _setup_exchanges(self) -> None:
        """Initialize CCXT exchange instances."""
        for source in self.sources:
            name = (
                source.name.lower() if hasattr(source, "name") else str(source).lower()
            )

            if not hasattr(ccxt, name):
                logger.warning(f"Exchange {name} not supported by CCXT")
                continue

            try:
                config = {"enableRateLimit": True, "timeout": 10000}

                # If source is contains additional credentials
                if hasattr(source, "api_key") and hasattr(source, "secret"):
                    config.update({"apiKey": source.api_key, "secret": source.secret})

                exchange_class = getattr(ccxt, name)
                self._exchanges[name] = exchange_class(config)
            except Exception as e:
                logger.error(f"Failed to initialize {name}: {str(e)}")

    async def get_rates(self) -> list[Rate]:
        """Fetch rates from configured exchanges."""
        tasks = []
        for exchange_id, exchange in self._exchanges.items():
            tasks.append(self._get_exchange_rate(exchange_id, exchange))

        rates = []
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Rate fetch error: {str(result)}")
                continue
            if result is not None:
                rates.append(result)

        return rates

    async def _get_exchange_rate(
        self, exchange_id: str, exchange: ccxt.Exchange
    ) -> Optional[Rate]:
        """Get rate from a single exchange."""
        try:
            async with self._semaphore:
                symbol = f"{self.base_asset}/{self.quote_asset}"

                # Load markets
                if not exchange.markets:
                    await exchange.load_markets()

                if symbol not in exchange.markets:
                    logger.warning(f"{symbol} not available on {exchange_id}")
                    return None

                ticker = await exchange.fetch_ticker(symbol)

                if not ticker or ticker.get("last") is None:
                    return None

                return Rate(
                    source=exchange_id,
                    price=float(ticker["last"]),
                    metadata={
                        "bid": ticker.get("bid"),
                        "ask": ticker.get("ask"),
                        "volume": ticker.get("baseVolume"),
                    },
                    timestamp=ticker.get("timestamp", time.time() * 1000) / 1000,
                )

        except Exception as e:
            logger.error(f"Error fetching from {exchange_id}: {str(e)}")
            return None
        finally:
            try:
                await exchange.close()
            except Exception:
                pass

    async def close(self) -> None:
        """Close all exchange connections."""
        for exchange in self._exchanges.values():
            try:
                await exchange.close()
            except Exception:
                pass
