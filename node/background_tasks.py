"""FastAPI background tasks."""

import asyncio
import logging
import time
from typing import NoReturn

from charli3_offchain_core.oracle.utils import asset_checks, common, state_checks

from node.config.models import AppConfig, RewardCollectionConfig, UpdaterConfig
from node.core.odv import OdvService

logger = logging.getLogger(__name__)


async def periodic_reward_calculator(
    config: UpdaterConfig,
    odv_service: OdvService,
    lock_for_reward_calculator: asyncio.Lock,
) -> NoReturn:
    """
    Run reward calculation handler indefinitely.
    """
    logger.info(
        f"Starting periodic_reward_calculator with time interval {config.reward_calculator_check_interval:.4f} seconds."
    )
    time_elapsed = float(0)

    while True:
        wait_time = max(config.reward_calculator_check_interval - time_elapsed, 0)

        time_elapsed = await run_reward_calculation_handler(
            config, odv_service, lock_for_reward_calculator, wait_time
        )


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


async def run_reward_calculation_handler(
    config: UpdaterConfig,
    odv_service: OdvService,
    lock_for_reward_calculator: asyncio.Lock,
    reward_calculation_delay: float | None = None,  # seconds
) -> float:
    """
    1. Wait some time interval (if any) to acquire the lock for handling the reward calculation;
    2. Check and attempt reward calculation
    3. Return elapsed time
    """
    if reward_calculation_delay:
        await asyncio.sleep(reward_calculation_delay)

    start_time = time.time()
    async with lock_for_reward_calculator:
        await check_and_attempt_reward_calculation(config, odv_service)

    time_elapsed = time.time() - start_time
    return time_elapsed


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


async def check_and_attempt_reward_calculation(
    config: UpdaterConfig,
    odv_service: OdvService,
) -> None:
    """
    Perform check of pending transport utxos and attempt reward calculation if needed:
    1. If the reward dismissing is close enough in time (configured by reward_calculation_dismissing_proximity)
    2. If there aren't enough empty transport utxos (configured by reward_calculation_empty_utxo_threshold)
    """
    try:
        utxos = await common.get_script_utxos(
            odv_service.oracle_script_address, odv_service.tx_manager
        )
        transports = asset_checks.filter_utxos_by_token_name(
            utxos, odv_service.oracle_policy_id, "C3RT"
        )
        pending_transports = state_checks.filter_pending_transports(transports)
        if not pending_transports:
            return

        empty_reward_transport_count = len(transports) - len(pending_transports)
        current_time = int(time.time_ns() * 1e-6)
        oldest_feed_timestamp: int = pending_transports[
            0
        ].output.datum.datum.aggregation.message.timestamp
        if (
            empty_reward_transport_count
            <= config.reward_calculation_empty_utxo_threshold
            or current_time
            >= (
                oldest_feed_timestamp
                + config.reward_calculation_dismissing_proximity * 1000
            )
        ):
            await odv_service.attempt_reward_calculation(
                config.reward_calculation_batch_size
            )

    except Exception as e:
        logger.error(f"Critical error on calculator background task process: {e}")


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
