"""FastAPI background tasks."""

import asyncio
import logging
import time
from typing import NoReturn

logger = logging.getLogger(__name__)


async def periodic_reward_calculator(
    lock_for_reward_calculator: asyncio.Lock,
    reward_calculator_check_interval: float,  # seconds
) -> NoReturn:
    """
    Call reward calculation handler indefinitely.
    """
    logger.info(
        f"Starting periodic_reward_calculator with time interval {reward_calculator_check_interval:.4f} seconds."
    )
    time_elapsed = float(0)

    while True:
        wait_time = max(reward_calculator_check_interval - time_elapsed, 0)

        time_elapsed = await run_reward_calculation_handler(
            lock_for_reward_calculator, wait_time
        )


async def run_reward_calculation_handler(
    lock_for_reward_calculator: asyncio.Lock,
    reward_calculation_delay: float | None = None,  # seconds
) -> float:
    if reward_calculation_delay:
        await asyncio.sleep(reward_calculation_delay)

    start_time = time.time()
    async with lock_for_reward_calculator:
        pass

    time_elapsed = time.time() - start_time
    return time_elapsed
