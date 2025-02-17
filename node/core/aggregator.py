"""Core rate aggregation functionality."""

import asyncio
import logging
from datetime import datetime
from statistics import median
from typing import Optional

import numpy as np
from node.config.models import ExchangeSource, RateConfig
from node.services.price_fetcher.base import BaseAdapter, Rate
from node.services.price_fetcher.ccxt import CCXTAdapter
from node.services.price_fetcher.charli3_dendrite import Charli3DendriteAdapter
from node.services.price_fetcher.generic_api import GenericAPIAdapter

logger = logging.getLogger(__name__)


class RateAggregator:
    """Main rate aggregation service."""

    def __init__(
        self,
        quote_currency: bool = False,
        quote_symbol: Optional[str] = None,
        min_sources: int = 3,
    ):
        """Initialize rate aggregator."""
        self.quote_currency = quote_currency
        self.quote_symbol = quote_symbol
        self.min_sources = min_sources
        self.base_adapters: list[BaseAdapter] = []
        self.quote_adapters: list[BaseAdapter] = []

    def detect_outliers(self, rates: list[float]) -> tuple[list[float], list[float]]:
        """Detect outliers using the Interquartile Range (IQR) method."""
        q1 = np.percentile(rates, 25)
        q3 = np.percentile(rates, 75)
        iqr = q3 - q1
        lower_bound = q1 - 3 * iqr
        upper_bound = q3 + 3 * iqr

        filtered_rates = [rate for rate in rates if lower_bound <= rate <= upper_bound]
        outliers = [rate for rate in rates if rate < lower_bound or rate > upper_bound]

        if outliers:
            logger.info("\n=== Outlier Detection ===")
            logger.info(f"Q1: {q1:.6f}, Q3: {q3:.6f}, IQR: {iqr:.6f}")
            logger.info(f"Bounds: [{lower_bound:.6f}, {upper_bound:.6f}]")
            logger.info(f"Outliers detected: {outliers}")
            logger.info(f"Filtered rates: {filtered_rates}")

        return filtered_rates, outliers

    def _log_rates_table(self, rates: list[Rate], title: str) -> None:
        """Display rates in a simplified formatted table."""
        headers = ["Provider", "Price ", "Quote Rate", "Timestamp"]
        separator = "-" * 90

        logger.info(f"\n=== {title} ===")
        logger.info(separator)
        logger.info("{:<15} {:<30} {:<15} {:<20}".format(*headers))
        logger.info(separator)

        for rate in rates:
            original_price = rate.metadata.get("original_price")
            quote_rate = rate.metadata.get("quote_rate", "N/A")
            timestamp = datetime.fromtimestamp(rate.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            if original_price:
                price_display = f"{rate.price:.6f} ({original_price:.6f})"
            else:
                price_display = f"{rate.price:.6f}"

            logger.info(
                "{:<15} {:<30} {:<15} {:<20}".format(
                    rate.source, price_display, quote_rate, timestamp
                )
            )

        logger.info(separator)

    async def _get_adapter_rates(
        self, adapter: BaseAdapter, quote_rate: Optional[float] = None
    ) -> list[Rate]:
        """Get rates from a single adapter with error handling."""
        try:
            rates = await adapter.get_rates()
            if not rates:
                return []

            processed_rates = []
            for rate in rates:
                if adapter.require_quote and quote_rate:

                    converted_rate = adapter.apply_quote(rate.price, quote_rate)
                    processed_rate = Rate(
                        source=rate.source,
                        price=converted_rate,
                        timestamp=rate.timestamp,
                        metadata={
                            **rate.metadata,
                            "original_price": rate.price,
                            "quote_rate": quote_rate,
                            "quote_method": adapter.quote_method,
                        },
                    )
                else:
                    processed_rate = rate
                processed_rates.append(processed_rate)
            self._log_rates_table(
                processed_rates,
                f"Rates from {adapter.__class__.__name__} | Asset: {adapter.base_asset}/{adapter.quote_asset}",
            )
            return processed_rates

        except Exception as e:
            logger.error(
                f"Error fetching from adapter {adapter.__class__.__name__}: {str(e)} | Asset: {adapter.base_asset}/{adapter.quote_asset}"
            )
            return []

    async def _fetch_rates_from_adapters(
        self, adapters: list[BaseAdapter], quote_rate: Optional[float] = None
    ) -> list[Rate]:
        """Fetch rates from a list of adapters in parallel."""
        rates_lists = await asyncio.gather(
            *(self._get_adapter_rates(adapter, quote_rate) for adapter in adapters)
        )
        return [rate for rates in rates_lists for rate in rates]

    async def fetch_all_rates(self) -> tuple[Optional[float], list[Rate]]:
        """Fetch and process all rates from configured adapters."""
        quote_rate = None

        # Fetch quote rates first if needed
        if self.quote_adapters:
            logger.info("\n=== Fetching Quote Rates ===")
            quote_rates = await self._fetch_rates_from_adapters(self.quote_adapters)

            if quote_rates:
                quote_prices = [rate.price for rate in quote_rates]
                filtered_quotes, _ = self.detect_outliers(quote_prices)
                if filtered_quotes:
                    quote_rate = median(filtered_quotes)
                    logger.info(f"\nMedian quote rate: {quote_rate}")
                else:
                    logger.warning("No valid quote rates after filtering")
                    if any(adapter.require_quote for adapter in self.base_adapters):
                        logger.error(
                            "Cannot proceed - quote rate required but not available"
                        )
                        return None, []

        # Process base rates
        logger.info("\n=== Fetching Base Rates ===")
        all_rates = await self._fetch_rates_from_adapters(
            self.base_adapters, quote_rate
        )

        if not all_rates:
            return None, []

        try:
            prices = [rate.price for rate in all_rates]
            filtered_prices, _ = self.detect_outliers(prices)

            if not filtered_prices:
                logger.warning("No valid rates after outlier filtering")
                return None, []

            # Filter rates but keep full Rate objects
            filtered_rates = [
                rate for rate in all_rates if rate.price in filtered_prices
            ]

            # Calculate median
            median_price = median(filtered_prices)
            return median_price, filtered_rates

        except Exception as e:
            logger.error(f"Error in rate processing: {str(e)}")
            return None, []

    def add_base_adapter(self, adapter: BaseAdapter) -> None:
        """Add a base rate adapter."""
        self.base_adapters.append(adapter)
        adapter.log_config()

    def add_quote_adapter(self, adapter: BaseAdapter) -> None:
        """Add a quote rate adapter."""
        self.quote_adapters.append(adapter)
        adapter.log_config()

    @classmethod
    def from_config(
        cls,
        config: RateConfig,
        min_sources: int = 1,
    ) -> "RateAggregator":
        """Create aggregator from configuration."""
        min_sources = (
            min_sources
            if min_sources is not None
            else (3 if config.min_requirement else 1)
        )

        aggregator = cls(
            quote_currency=bool(config.quote_currency),
            quote_symbol=config.general_quote_symbol,
            min_sources=min_sources,
        )

        def initialize_adapter(exchange: ExchangeSource, is_base: bool):
            """Helper function to initialize the correct adapter."""
            adapter_map = {
                "charli3-dendrite": Charli3DendriteAdapter,
                "ccxt": CCXTAdapter,
                "generic-api": GenericAPIAdapter,
            }

            adapter_class = adapter_map.get(exchange.adapter.lower())
            if not adapter_class:
                raise ValueError(f"Unsupported adapter type: {exchange.adapter}")

            adapter = adapter_class(
                base_asset=exchange.asset_a,
                quote_asset=exchange.asset_b,
                sources=exchange.sources,
                require_quote=exchange.quote_required,
                quote_method=exchange.quote_calc_method,
            )

            if is_base:
                aggregator.add_base_adapter(adapter)
            else:
                aggregator.add_quote_adapter(adapter)

        # Initialize base adapters
        for exchange in config.base_currency.exchanges:
            initialize_adapter(exchange, is_base=True)

        # Initialize quote adapters if present
        if config.quote_currency:
            for exchange in config.quote_currency.exchanges:
                initialize_adapter(exchange, is_base=False)

        return aggregator
