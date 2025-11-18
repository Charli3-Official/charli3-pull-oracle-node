"""FastAPI background tasks."""

import asyncio
import logging
import time
from typing import NoReturn

from charli3_offchain_core.oracle.utils import common, state_checks

from node.config.models import AppConfig, RewardCollectionConfig
from node.core.odv import OdvService

logger = logging.getLogger(__name__)


async def periodic_node_collect(
    config: AppConfig,
    odv_service: OdvService,
    lock_for_node_collect: asyncio.Lock,
) -> NoReturn:
    """
    Run node collect handler indefinitely.
    """
    logger.info(
        f"Starting periodic_node_collect with check interval {config.updater.reward_collect_check_interval:.4f} seconds."
    )
    time_elapsed = float(0)

    while True:
        # Check for node collect at configured interval
        wait_time = max(config.updater.reward_collect_check_interval - time_elapsed, 0)

        time_elapsed = await run_node_collect_handler(
            config, odv_service, lock_for_node_collect, wait_time
        )


async def run_node_collect_handler(
    config: AppConfig,
    odv_service: OdvService,
    lock_for_node_collect: asyncio.Lock,
    node_collect_delay: float | None = None,  # seconds
) -> float:
    """
    1. Wait some time interval (if any) to acquire the lock for handling the node collect;
    2. Check and attempt node collect
    3. Return elapsed time
    """
    if node_collect_delay:
        await asyncio.sleep(node_collect_delay)

    start_time = time.time()
    async with lock_for_node_collect:
        await check_and_attempt_node_collect(config.reward_collection, odv_service)

    time_elapsed = time.time() - start_time
    return time_elapsed


async def check_and_attempt_node_collect(
    config: RewardCollectionConfig,
    odv_service: OdvService,
) -> None:
    """
    Check if the node's reward amount meets the trigger threshold and attempt node collect if needed.
    """
    try:
        # Get contract UTXOs
        utxos = await common.get_script_utxos(
            odv_service.oracle_script_address, odv_service.tx_manager
        )

        # Get reward account datum
        reward_account_datum, _ = state_checks.get_reward_account_by_policy_id(
            utxos, odv_service.oracle_policy_id
        )

        # Get oracle settings to find node index
        settings_datum, _ = state_checks.get_oracle_settings_by_policy_id(
            utxos, odv_service.oracle_policy_id
        )

        # Find the node's index
        payment_vkhs = list(settings_datum.nodes.node_map.values())
        try:
            node_index = payment_vkhs.index(odv_service.node_payment_vk.hash())
        except ValueError:
            logger.warning("Node not registered in oracle settings")
            return

        # Get the node's reward amount
        node_reward = reward_account_datum.nodes_to_rewards[node_index]

        # Check if reward meets trigger amount
        if node_reward >= config.trigger_amount:
            await odv_service.attempt_node_collect(contract_utxos=utxos)
        else:
            logger.debug(
                f"Node reward {node_reward} below trigger {config.trigger_amount}"
            )

    except Exception as e:
        logger.error(f"Critical error on node collect background task process: {e}")
