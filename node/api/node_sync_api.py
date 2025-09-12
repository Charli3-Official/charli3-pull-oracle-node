"""Syncing with Charli3 Central DB."""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger("node_sync_api")
logging.Formatter.converter = time.gmtime


class NodeSyncApi:
    """Class to interact with the NodeSync API."""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url

    async def _post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Post data to the API endpoint."""
        if not self.api_url:
            return {"status": "no_api_url"}

        url = f"{self.api_url.rstrip('/')}{path}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=data, headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {"status": "success", "data": result}
                    else:
                        error_text = await response.text()
                        return {
                            "status": "error",
                            "code": response.status,
                            "message": error_text,
                        }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def report_initialization(
        self,
        config,  # Your AppConfig object
        node_keys,  # Your node keys from load_keys()
    ) -> Dict[str, Any]:
        """Report feed and node initialization data to the central db."""
        try:
            # Extract data from your config structure
            feed_data = {
                "feedAddress": config.node.oracle_address,
                "symbol": config.rate.general_base_symbol,
                "aggStateNFT": config.node.oracle_currency,  # Using oracle_currency as NFT
                "oracleNFT": config.node.oracle_currency,
                "rewardNFT": config.node.reward_token_hash
                or config.node.oracle_currency,
                "nodeNFT": config.node.oracle_currency,
                "oracleMintingCurrency": config.node.oracle_currency,
            }

            # Extract node data from your keys
            (
                node_feed_sk,
                node_feed_vk,
                node_feed_vkh,
                node_payment_sk,
                node_payment_vk,
                node_payment_vkh,
            ) = node_keys

            node_data = {
                "pubKeyHash": node_feed_vkh.payload.hex(),
                "nodeOperatorAddress": config.node.oracle_address,
                "feedAddress": config.node.oracle_address,
            }

            # Extract providers from your rate config
            providers_data = []
            for exchange in config.rate.base_currency.exchanges:
                for source in exchange.sources:
                    provider_data = {
                        "providerId": str(uuid.uuid4()),
                        "feedAddress": config.node.oracle_address,
                        "name": source.name,
                        "apiUrl": source.api_url or "",
                        "path": "/".join(str(p) for p in (source.json_path or [])),
                        "token": source.headers.get("Authorization", ""),
                        "adapterType": exchange.adapter,
                    }
                    providers_data.append(provider_data)

            # Prepare the data payload with exact same format
            data = {
                "feed": feed_data,
                "node": node_data,
                "providers": providers_data,
            }

            path = "/api/node-updater/initialize"
            response = await self._post(path=path, data=data)
            logger.info("Successfully reported initialization: %s", response)
            return response
        except Exception as e:
            logger.error("Failed to report initialization: %s", e)
            return {"status": "error", "message": str(e)}

    async def report_update(
        self,
        config,  # Your AppConfig object
        tx_hash: str,
        updated_value: float,
        rate_aggregation_id: str,
        trigger: str,
        status: str = "SUCCESS",
        rate_data_flow: List[Dict[str, Any]] = None,
        aggregated_rate: float = None,
    ) -> Dict[str, Any]:
        """Report node update data to the central db."""
        try:
            path = "/api/node-updater/reportAll"

            # Prepare node update data from your config
            node_update_data = {
                "txHash": tx_hash,
                "nodeAddress": config.node.oracle_address,
                "feedAddress": config.node.oracle_address,
                "timestamp": time.time(),
                "status": status,
                "updatedValue": updated_value,
                "rateAggregationId": rate_aggregation_id,
                "trigger": trigger,
            }

            # Use provided rate data flow or create empty list
            rate_data_flow_list = rate_data_flow or []

            # Prepare aggregated rate details
            aggregated_rate_details = {
                "feedAddress": config.node.oracle_address,
                "requestedAt": time.time(),
                "aggregationTimestamp": time.time(),
                "aggregatedRate": aggregated_rate or updated_value,
                "method": "median",
            }

            # Full data payload in exact same format
            data = {
                "nodeUpdate": node_update_data,
                "rateDataFlow": rate_data_flow_list,
                "aggregatedRateDetails": aggregated_rate_details,
            }

            response = await self._post(path=path, data=data)
            logger.info("Successfully reported node update: %s", response)
            return response

        except Exception as e:
            logger.error("Failed to report node update: %s", e, exc_info=True)
            return {"status": "error", "message": str(e)}
