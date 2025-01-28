import logging
from typing import Any, Optional, Tuple

from charli3_offchain_core.blockchain.transactions import TransactionManager
from charli3_offchain_core.models.oracle_datums import (
    AggStateVariant,
    OracleSettingsDatum,
    RewardTransportVariant,
)
from charli3_offchain_core.oracle.utils.common import get_script_utxos, try_parse_datum
from charli3_offchain_core.oracle.utils.state_checks import (
    get_oracle_settings_by_policy_id,
    is_oracle_paused,
)
from charli3_offchain_core.oracle.validations.aggregation import (
    validate_median_calculation,
    validate_node_rewards,
    validate_node_signatures,
)
from pycardano import PaymentVerificationKey, ScriptHash, Transaction

from .errors import (
    InvalidNodeSignatureError,
    NodeNotRegisteredError,
    OraclePausedError,
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


async def validate_aggregate_tx(
    tx_manager: TransactionManager,
    oracle_addr: str,
    tx: Transaction,
    signed_messages: dict[str, Any],
) -> None:
    """
    Validate complete ODV aggregate transaction.

    Args:
        tx_manager: Transaction manager instance
        oracle_addr: Oracle script address
        tx: Transaction to validate
        signed_messages: dict of node verification key hex -> signed message data

    Returns:
        None
    """
    try:
        policy_ids = {data["oracle_nft_policy_id"] for data in signed_messages.values()}
        if len(policy_ids) != 1:
            raise ValidationError("Mismatch in oracle_nft_policy_id across messages")

        policy_id = policy_ids.pop()

        utxos = await get_script_utxos(oracle_addr, tx_manager)
        settings_datum, _ = get_oracle_settings_by_policy_id(
            utxos, ScriptHash(bytes.fromhex(policy_id))
        )

        transport_datum, agg_state_datum = None, None

        for output in tx.transaction_body.outputs:
            if str(output.address) != oracle_addr or not output.datum:
                continue

            if transport_datum is None:
                transport_datum = try_parse_datum(output.datum, RewardTransportVariant)
            if agg_state_datum is None:
                agg_state_datum = try_parse_datum(output.datum, AggStateVariant)

            if transport_datum and agg_state_datum:
                break

        if not transport_datum or not agg_state_datum:
            raise ValidationError("Missing or invalid transaction datums")

        # Validate node signatures
        is_valid, error = validate_node_signatures(signed_messages)
        if not is_valid:
            raise InvalidNodeSignatureError(error)

        # Validate median calculation
        is_valid, error = validate_median_calculation(
            transport_datum.datum, signed_messages
        )
        if not is_valid:
            raise ValidationError(error)

        # Validate rewards
        is_valid, error = validate_node_rewards(
            transport_datum.datum.aggregation, settings_datum
        )
        if not is_valid:
            raise ValidationError(error)

    except (ValidationError, InvalidNodeSignatureError) as e:
        raise e
    except Exception as e:
        raise ValidationError(f"Transaction validation error: {str(e)}")
