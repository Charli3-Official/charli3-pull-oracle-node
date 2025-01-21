import logging
from datetime import datetime
from typing import Optional, Tuple

from charli3_offchain_core.blockchain.transactions import TransactionManager
from charli3_offchain_core.models.oracle_datums import OracleSettingsDatum
from charli3_offchain_core.oracle.utils.common import get_script_utxos
from charli3_offchain_core.oracle.utils.state_checks import (
    get_oracle_settings_by_policy_id,
    is_oracle_paused,
)
from pycardano import PaymentVerificationKey, ScriptHash

from .errors import (
    NodeNotRegisteredError,
    OraclePausedError,
    TimestampValidationError,
    ValidationError,
)

logger = logging.getLogger(__name__)


async def validate_node_registration(
    tx_manager: TransactionManager,
    oracle_addr: str,
    node_vk: PaymentVerificationKey,
    oracle_nft_policy_id: str,
) -> Tuple[bool, Optional[OracleSettingsDatum]]:
    """
    Validate node registration and oracle status

    Args:
        tx_manager: Transaction manager instance
        oracle_addr: Oracle script address
        node_vk: Node verification key
        oracle_nft_policy_id: Oracle NFT policy ID

    Returns:
        Tuple of validation status and oracle settings

    Raises:
        ValidationError: If oracle settings not found
        OraclePausedError: If oracle is paused
        NodeNotRegisteredError: If node is not registered
    """
    try:
        utxos = await get_script_utxos(oracle_addr, tx_manager)
        policy_hash = ScriptHash(bytes.fromhex(oracle_nft_policy_id))

        settings_datum, settings_utxo = get_oracle_settings_by_policy_id(
            utxos, policy_hash
        )
        if settings_utxo is None:
            raise ValidationError("Oracle settings not found")

        if is_oracle_paused(settings_datum):
            raise OraclePausedError("Oracle is currently paused")

        node_hash = node_vk.hash()
        if node_hash not in settings_datum.nodes.node_map:
            raise NodeNotRegisteredError(
                f"Node {node_hash.to_primitive().hex()[:8]} not registered"
            )

        return True, settings_datum

    except (ValidationError, OraclePausedError, NodeNotRegisteredError):
        raise
    except Exception as e:
        raise ValidationError(f"Validation failed: {str(e)}")


def validate_timestamp(tx_validity: dict[str, int], timestamp: int) -> None:
    """
    Validate timestamp is within transaction validity interval

    Args:
        tx_validity: dict with start and end timestamps
        timestamp: int timestamp to validate

    Raises:
        TimestampValidationError: If timestamp is outside validity interval
    """
    start = tx_validity.start if hasattr(tx_validity, "start") else tx_validity["start"]
    end = tx_validity.end if hasattr(tx_validity, "end") else tx_validity["end"]

    if not start <= timestamp <= end:
        raise TimestampValidationError(
            f"Timestamp {timestamp} outside validity interval " f"[{start}, {end}]"
        )


def get_current_timestamp() -> int:
    """Get current timestamp in milliseconds"""
    return int(datetime.now().timestamp() * 1000)
