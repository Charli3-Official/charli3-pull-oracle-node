import json
import logging
import time

from locust import HttpUser, between, events, task

from tests.performance.common.config import (
    load_locust_config,
    setup_chain_query_and_tx_manager,
)
from tests.performance.common.mock_data import get_feed_request_data

logger = logging.getLogger(__name__)

chain_query = None
tx_manager = None


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initializes necessary components before test start."""
    global chain_query, tx_manager

    logger.info("Setting up ChainQuery and TransactionManager")
    try:
        config_dict = load_locust_config()
        chain_query, tx_manager = setup_chain_query_and_tx_manager(config_dict)
        logger.info("ChainQuery and TransactionManager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise


class FeedAPIUser(HttpUser):
    """User class for testing Feed API endpoints."""

    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks

    def on_start(self):
        """Validates setup before starting tests."""
        logger.info("Starting Feed API User")
        if not chain_query or not tx_manager:
            logger.error("Required components not initialized")
            raise RuntimeError("ChainQuery and TransactionManager must be initialized")

    @task(1)
    def get_feed(self):
        """Tests the ODV feed endpoint."""
        request_data = get_feed_request_data(tx_manager)

        # Send request and measure
        start_time = time.time()
        with self.client.post(
            "/odv/feed", json=request_data, catch_response=True, name="/odv/feed"
        ) as response:
            duration = time.time() - start_time

            try:
                if response.status_code == 200:
                    _ = response.json()
                    logger.debug(f"Feed response received in {duration:.2f}s")
                    response.success()
                else:
                    logger.warning(f"Feed request failed: {response.status_code}")
                    response.failure(f"Failed with status {response.status_code}")
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response: {response.text}")
                response.failure("Invalid JSON response")
            except Exception as e:
                logger.error(f"Error processing response: {e}")
                response.failure(f"Error: {str(e)}")
