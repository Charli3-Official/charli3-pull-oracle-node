import logging
from typing import Any, Dict

from tests.performance.common.config import load_locust_config

logger = logging.getLogger(__name__)


def get_feed_request_data(tx_manager) -> Dict[str, Any]:
    """Generates request data for feed endpoint."""
    config = load_locust_config()
    validity_length = config.get("odv_validity_length", 170000)
    policy_id = config.get("policy_id", "")

    validity_window = tx_manager.calculate_validity_window(validity_length)

    return {
        "oracle_nft_policy_id": policy_id,
        "tx_validity_interval": {
            "start": validity_window.validity_start,
            "end": validity_window.validity_end,
        },
    }
