"""FastAPI application entrypoint."""

import asyncio
import logging
from contextlib import asynccontextmanager

import click
import uvicorn
from fastapi import FastAPI

from node.api.dependencies import initialize_odv_service
from node.api.endpoints import health, odv
from node.background_tasks import periodic_node_collect
from node.config.models import AppConfig
from node.config.setup import (
    initialize_node_sync,
    load_config,
    load_keys,
    setup_chain_query_and_tx_manager,
    setup_dendrite_backend,
    setup_node_sync,
)
from node.core.aggregator import RateAggregator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    node_collect_task = None

    try:
        # Startup
        logger.info("Starting ODV Oracle Node...")
        config: AppConfig = app.state.config

        # Setup core services
        if not setup_dendrite_backend(config):
            raise RuntimeError("Failed to setup Dendrite backend")
        await asyncio.sleep(1)

        # Initialize core components
        rate_aggregator = RateAggregator.from_config(
            config=config.rate, cache_config=config.cache
        )

        node_keys = load_keys(config)
        (
            node_feed_sk,
            node_feed_vk,
            node_feed_vkh,
            node_payment_sk,
            node_payment_vk,
            _,
        ) = node_keys

        chain_query, tx_manager = setup_chain_query_and_tx_manager(config)

        node_sync_api = setup_node_sync(config, node_keys)

        # Initialize ODV service
        odv_service = await initialize_odv_service(
            rate_aggregator=rate_aggregator,
            chain_query=chain_query,
            tx_manager=tx_manager,
            oracle_addr=config.node.oracle_address,
            oracle_curr=config.node.oracle_currency,
            node_feed_sk=node_feed_sk,
            node_feed_vk=node_feed_vk,
            node_feed_vkh=node_feed_vkh,
            node_payment_sk=node_payment_sk,
            node_payment_vk=node_payment_vk,
            reward_token_hash=config.node.reward_token_hash,
            reward_token_name=config.node.reward_token_name,
            reward_destination_address=config.reward_collection.reward_destination_address,
            create_collateral=config.reward_collection.create_collateral,
            ref_script_config=config.reference_script,
        )

        if node_sync_api:
            odv_service.node_sync_api = node_sync_api

        # Initialize NodeSync (report initialization)
        await initialize_node_sync(config, node_keys, node_sync_api)
        # Initialize background tasks
        lock_for_node_collect = asyncio.Lock()
        loop = asyncio.get_event_loop()
        node_collect_task = loop.create_task(
            periodic_node_collect(
                config,
                odv_service,
                lock_for_node_collect,
            )
        )

        logger.info("ODV Oracle Node started successfully")
        yield {
            "app_config": config,
            "lock_for_node_collect": lock_for_node_collect,
        }

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        logger.info("Shutting down ODV Oracle Node...")
        # Cancel background tasks when main task stops
        if node_collect_task is not None:
            try:
                node_collect_task.cancel()
            except Exception:
                logger.debug("Failed to cancel node_collect_task", exc_info=True)


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
    app.include_router(health.router, tags=["health"])

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
