"""FastAPI background tasks."""

import asyncio
import logging
import time
from typing import NoReturn

from charli3_offchain_core.oracle.utils import common, state_checks, asset_checks

from node.config.models import UpdaterConfig
from node.core.odv import OdvService

logger = logging.getLogger(__name__)


async def periodic_reward_calculator(
    config: UpdaterConfig,
    odv_service: OdvService,
    lock_for_reward_calculator: asyncio.Lock,
) -> NoReturn:
    """
    Call reward calculation handler indefinitely.
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


async def run_reward_calculation_handler(
    config: UpdaterConfig,
    odv_service: OdvService,
    lock_for_reward_calculator: asyncio.Lock,
    reward_calculation_delay: float | None = None,  # seconds
) -> float:
    if reward_calculation_delay:
        await asyncio.sleep(reward_calculation_delay)

    start_time = time.time()
    async with lock_for_reward_calculator:
        await check_and_attempt_reward_calculation(config, odv_service)

    time_elapsed = time.time() - start_time
    return time_elapsed


async def check_and_attempt_reward_calculation(
    config: UpdaterConfig,
    odv_service: OdvService,
):
    utxos = await common.get_script_utxos(
        odv_service.odv_tx_builder.script_address, odv_service.tx_manager
    )
    transports = asset_checks.filter_utxos_by_token_name(
        utxos, odv_service.odv_tx_builder.policy_id, "C3RT"
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
        empty_reward_transport_count <= config.reward_calculation_empty_utxo_threshold
        or current_time
        >= (
            oldest_feed_timestamp
            + config.reward_calculation_dismissing_proximity * 1000
        )
    ):
        await odv_service.attempt_reward_calculation(
            config.reward_calculation_batch_size
        )
