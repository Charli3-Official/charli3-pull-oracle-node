"""Generic API adapter for custom rate sources."""

import asyncio
import logging
import time
from typing import Any, Optional, Union

import aiohttp
from node.config.models import SourceConfig
from yarl import URL

from node.services.price_fetcher.base import BaseAdapter, Rate

logger = logging.getLogger(__name__)


class GenericAPIAdapter(BaseAdapter):
    """Adapter for fetching rates from custom API endpoints."""

    def __init__(
        self,
        base_asset: str,
        quote_asset: str,
        sources: list[Union[dict[str, Any], SourceConfig]],
        require_quote: bool = False,
        quote_method: str = "multiply",
        timeout: float = 10.0,
        max_retries: int = 2,
    ):
        """Initialize Generic API adapter."""

        for source in sources:

            if isinstance(source, SourceConfig):
                if not (source.name and source.api_url and source.json_path):
                    raise ValueError(
                        f"Invalid config for {source.name}: missing required fields"
                    )
                # Validate URL
                try:
                    URL(source.api_url)
                except Exception as e:
                    raise ValueError(f"Invalid URL for {source.name}: {str(e)}")
            else:
                if not all(k in source for k in ["name", "url", "json_path"]):
                    raise ValueError(
                        f"Invalid config for {source.get('name', 'Unknown')}"
                    )
                try:
                    URL(source["url"])
                except Exception as e:
                    raise ValueError(f"Invalid URL for {source['name']}: {str(e)}")

        super().__init__(base_asset, quote_asset, sources, require_quote, quote_method)
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    async def get_rates(self) -> list[Rate]:
        """Fetch rates from all configured sources."""
        async with aiohttp.ClientSession() as session:
            tasks = [self._get_source_rate(session, source) for source in self.sources]

            rates = []
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Rate fetch error: {str(result)}")
                    continue
                if result is not None:
                    rates.append(result)

        return rates

    async def _get_source_rate(
        self,
        session: aiohttp.ClientSession,
        source: Union[dict[str, Any], SourceConfig],
    ) -> Optional[Rate]:
        """Get rate from a single source with retries."""
        for attempt in range(self.max_retries):
            try:
                return await self._fetch_rate(session, source)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    source_name = (
                        source.name
                        if isinstance(source, SourceConfig)
                        else source["name"]
                    )
                    logger.error(
                        f"Failed to fetch from {source_name} "
                        f"after {self.max_retries} attempts: {str(e)}"
                    )
                    return None
                await asyncio.sleep(1)

    async def _fetch_rate(
        self,
        session: aiohttp.ClientSession,
        source: Union[dict[str, Any], SourceConfig],
    ) -> Optional[Rate]:
        """Fetch and parse rate from a single source."""
        try:
            if isinstance(source, SourceConfig):
                name = source.name
                url = source.api_url
                json_path = source.json_path
                headers = source.headers
            else:
                name = source["name"]
                url = source["url"]
                json_path = source["json_path"]
                headers = source.get("headers", {})

            async with session.get(
                url=url, headers=headers, timeout=self.timeout
            ) as response:
                if response.status != 200:
                    logger.warning(
                        f"HTTP {response.status} from {name}: "
                        f"{await response.text()}"
                    )
                    return None

                data = await response.json()
                price = self._extract_price(data, json_path)

                if price is None:
                    return None

                return Rate(
                    source=name,
                    price=float(price),
                    metadata={"url": str(response.url), "response_time": time.time()},
                    timestamp=time.time(),
                )

        except Exception as e:
            source_name = (
                source.name if isinstance(source, SourceConfig) else source["name"]
            )
            logger.error(f"Error fetching from {source_name}: {str(e)}")
            return None

    def _extract_price(
        self, data: Any, json_path: list[Union[str, int]]
    ) -> Optional[float]:
        """Extract price value from JSON response."""
        try:
            for key in json_path:
                data = data[key]
            return float(data)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Error extracting price: {str(e)}")
            return None
