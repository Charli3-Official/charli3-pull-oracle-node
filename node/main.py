"""FastAPI application entrypoint."""

import asyncio
import logging
from contextlib import asynccontextmanager

import click
import uvicorn
from node.api.dependencies import initialize_odv_service
from node.api.endpoints import odv
from node.config.models import AppConfig
from node.config.setup import (
    load_config,
    load_keys,
    setup_chain_query_and_tx_manager,
    setup_dendrite_backend,
)
from node.core.aggregator import RateAggregator
from fastapi import FastAPI

from node.background_tasks import periodic_reward_calculator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    try:
        # Startup
        logger.info("Starting ODV Oracle Node...")
        config: AppConfig = app.state.config

        # Setup core services
        if not setup_dendrite_backend(config):
            raise RuntimeError("Failed to setup Dendrite backend")
        await asyncio.sleep(1)

        # Initialize core components
        rate_aggregator = RateAggregator.from_config(config=config.rate)
        node_feed_sk, node_feed_vk, _, node_payment_sk, node_payment_vk, _ = load_keys(
            config
        )
        chain_query, tx_manager = setup_chain_query_and_tx_manager(config)

        # Initialize ODV service
        odv_service = await initialize_odv_service(
            rate_aggregator=rate_aggregator,
            chain_query=chain_query,
            tx_manager=tx_manager,
            oracle_addr=config.node.oracle_address,
            oracle_curr=config.node.oracle_currency,
            node_feed_sk=node_feed_sk,
            node_feed_vk=node_feed_vk,
            node_payment_sk=node_payment_sk,
            node_payment_vk=node_payment_vk,
            reward_token_hash=config.node.reward_token_hash,
            reward_token_name=config.node.reward_token_name,
        )

        # Initialize background tasks
        lock_for_reward_calculator = asyncio.Lock()
        loop = asyncio.get_event_loop()
        reward_calculator_task = loop.create_task(
            periodic_reward_calculator(
                config.updater,
                odv_service,
                lock_for_reward_calculator,
            )
        )

        logger.info("ODV Oracle Node started successfully")
        yield {
            "app_config": config,
            "lock_for_reward_calculator": lock_for_reward_calculator,
        }

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        logger.info("Shutting down ODV Oracle Node...")
        # Cancel background tasks when main task stops
        if reward_calculator_task is not None:
            reward_calculator_task.cancel()


def create_app(config: AppConfig) -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Charli3 ODV Oracle Node",
        description="On-Demand Validation (ODV) Oracle Node API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Store config
    app.state.config = config

    # Register routers
    app.include_router(odv.router, prefix="/odv", tags=["odv"])

    return app


def start_app(config_path: str, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Initialize and start the application server."""
    try:
        config = load_config(config_path)
        app = create_app(config)
        uvicorn.run(app, host=host, port=port, log_level="info")
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise click.ClickException(str(e))


@click.group()
def cli():
    """Charli3 ODV Oracle Node CLI."""
    pass


@cli.command()
@click.option("--config", "-c", required=True, help="Path to configuration file")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to bind to")
def run(config: str, host: str, port: int):
    """Run the ODV Oracle Node service."""
    start_app(config, host, port)


if __name__ == "__main__":
    cli()
