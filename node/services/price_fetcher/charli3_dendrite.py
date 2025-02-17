"""Dendrite adapter for DEX rates."""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Optional, Type, Union

from charli3_dendrite import (
    MinswapCPPState,
    MinswapV2CPPState,
    MuesliSwapCPPState,
    SpectrumCPPState,
    SundaeSwapCPPState,
    SundaeSwapV3CPPState,
    VyFiCPPState,
    WingRidersCPPState,
)
from charli3_dendrite.backend import get_backend
from charli3_dendrite.dexs.amm.amm_base import AbstractPoolState
from node.config.models import SourceConfig

from node.services.price_fetcher.base import BaseAdapter, Rate

logger = logging.getLogger(__name__)

DEX_STATES: dict[str, Type[AbstractPoolState]] = {
    "sundaeswapv3": SundaeSwapV3CPPState,
    "sundaeswap": SundaeSwapCPPState,
    "spectrum": SpectrumCPPState,
    "minswap": MinswapCPPState,
    "minswapv2": MinswapV2CPPState,
    "wingriders": WingRidersCPPState,
    "muesliswap": MuesliSwapCPPState,
    "vyfi": VyFiCPPState,
}


class Charli3DendriteAdapter(BaseAdapter):
    """Adapter for fetching DEX rates using Dendrite."""

    def __init__(
        self,
        base_asset: str,
        quote_asset: str,
        sources: list[Union[str, SourceConfig]],
        require_quote: bool = False,
        quote_method: str = "multiply",
    ):
        """Initialize Dendrite adapter.

        Args:
            base_asset: Base asset hash/id
            quote_asset: Quote asset hash/id
            sources: list of DEX names or SourceConfig objects
            require_quote: Whether quote conversion is needed
            quote_method: Quote calculation method
        """
        source_names = [s.name if hasattr(s, "name") else s for s in sources]
        # Validate DEX sources
        invalid_dexes = [s for s in source_names if s.lower() not in DEX_STATES]
        if invalid_dexes:
            raise ValueError(f"Unsupported DEXes: {', '.join(invalid_dexes)}")

        super().__init__(base_asset, quote_asset, sources, require_quote, quote_method)
        self.backend = get_backend()
        self._asset_names = self._get_asset_names()

    async def get_rates(self) -> list[Rate]:
        """Fetch rates from configured DEXes."""
        # Extract source names
        source_names = [
            s.name.lower() if hasattr(s, "name") else str(s).lower()
            for s in self.sources
        ]

        tasks = [self._get_dex_rate(dex) for dex in source_names]
        rates = []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"DEX rate error: {str(result)}")
                continue
            if result is not None:
                rates.append(result)

        return rates

    async def _get_dex_rate(self, dex_name: str) -> Optional[Rate]:
        """Get rate from a single DEX."""
        try:
            dex_class = DEX_STATES[dex_name]

            # Handle VyFi's special case
            if dex_name == "vyfi":
                selector = dex_class.pool_selector(
                    assets=[self.base_asset, self.quote_asset]
                ).model_dump()
                assets = selector.pop("assets", [])
            else:
                selector = dex_class.pool_selector().model_dump()
                assets = selector.pop("assets") or []
                assets.extend(
                    [a for a in [self.base_asset, self.quote_asset] if a != "lovelace"]
                )

            # Get pool data
            pools = await asyncio.to_thread(
                self.backend.get_pool_utxos,
                limit=10,
                assets=assets,
                historical=False,
                **selector,
            )

            for pool_data in pools:
                try:
                    pool = dex_class.model_validate(pool_data.model_dump())
                    price = self._get_pool_price(
                        pool, [self.base_asset, self.quote_asset]
                    )

                    if price is not None:
                        return Rate(
                            source=dex_name,
                            price=float(price),
                            metadata={
                                "pool_id": pool.pool_id,
                                "liquidity": self._get_liquidity(pool),
                            },
                            timestamp=time.time(),
                        )
                except Exception as e:
                    logger.warning(f"Invalid pool in {dex_name}: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error from {dex_name}: {str(e)}")

        return None

    def _get_pool_price(self, pool: Any, assets: list[str]) -> Optional[Decimal]:
        """Get price from pool data."""
        try:
            pool_assets = pool.assets.model_dump()
            price_a_to_b, price_b_to_a = pool.price

            asset_a = list(pool_assets.keys())[0]
            asset_b = list(pool_assets.keys())[1]

            if assets[0] in asset_a and assets[1] in asset_b:
                return price_b_to_a
            if assets[0] in asset_b and assets[1] in asset_a:
                return price_a_to_b

        except Exception as e:
            logger.warning(f"Error extracting pool price: {str(e)}")

        return None

    def _get_liquidity(self, pool: Any) -> dict[str, int]:
        """Get pool liquidity information."""
        try:
            assets = pool.assets.model_dump()
            return {
                token: amount
                for token, amount in assets.items()
                if token in [self.base_asset, self.quote_asset]
            }
        except Exception as e:
            logger.warning(f"Error getting liquidity: {str(e)}")
            return {}

    def _get_asset_names(self) -> dict[str, str]:
        """Get human-readable asset names."""
        names = {}
        for asset in [self.base_asset, self.quote_asset]:
            if asset == "lovelace":
                names[asset] = "ADA"
            else:
                try:
                    # Handle CIP-68 format
                    hex_name = asset[56:]
                    raw_bytes = bytes.fromhex(hex_name)
                    if len(raw_bytes) > 4:
                        names[asset] = raw_bytes[4:].decode("utf-8")
                    else:
                        names[asset] = raw_bytes.decode("utf-8")
                except Exception:
                    names[asset] = asset
        return names
