import hashlib
import logging
from typing import Any

import charli3_offchain_core.oracle.aggregate.builder as odv_builder
from charli3_offchain_core.blockchain.chain_query import ChainQuery
from charli3_offchain_core.blockchain.transactions import TransactionManager
from charli3_offchain_core.models.base import TxValidityInterval
from charli3_offchain_core.models.message import (
    OracleNodeMessage,
    SignedOracleNodeMessage,
)
from charli3_offchain_core.oracle.exceptions import (
    NoPendingTransportUtxosFoundError,
    RewardCalculationIsNotSubsidizedError,
    TransactionError,
)
from charli3_offchain_core.oracle.validations.aggregation import (
    validate_is_node_registered,
    validate_node_message_signatures,
    validate_node_updates_and_aggregation_median,
    validate_policy_id_in_messages,
    validate_timestamp,
    validate_transaction_datums,
)
from pycardano import (
    Address,
    AssetName,
    ExtendedSigningKey,
    PaymentExtendedSigningKey,
    PaymentVerificationKey,
    ScriptHash,
    Transaction,
    TransactionBody,
    TransactionWitnessSet,
    VerificationKey,
)

from node.core.aggregator import RateAggregator
from node.core.errors import NodeServiceError, RateAggregationError, ValidationError

logger = logging.getLogger(__name__)


class OdvService:
    """Service handling ODV (On-Demand Validation) operations"""

    def __init__(
        self,
        rate_aggregator: RateAggregator,
        chain_query: ChainQuery,
        tx_manager: TransactionManager,
        oracle_addr: str,
        oracle_curr: str,
        node_feed_sk: ExtendedSigningKey,
        node_feed_vk: VerificationKey,
        node_payment_sk: PaymentExtendedSigningKey,
        node_payment_vk: PaymentVerificationKey,
        reward_token_hash: str | None = None,
        reward_token_name: str | None = None,
        check_if_reward_calculation_fee_subsidized: bool = False,
    ):
        self.rate_aggregator = rate_aggregator
        self.chain_query = chain_query
        self.tx_manager = tx_manager
        self.oracle_addr = oracle_addr
        self.oracle_curr = oracle_curr
        self.reward_token_hash = reward_token_hash
        self.reward_token_name = reward_token_name
        self.check_if_reward_calculation_fee_subsidized = (
            check_if_reward_calculation_fee_subsidized
        )
        self.node_feed_sk = node_feed_sk
        self.node_feed_vk = node_feed_vk
        self.node_payment_sk = node_payment_sk
        self.node_payment_vk = node_payment_vk
        self.network = self.chain_query.context.network
        self.node_payment_addr = Address(
            payment_part=self.node_payment_vk.hash(), network=self.network
        )
        self.odv_tx_builder = odv_builder.OracleTransactionBuilder(
            tx_manager=self.tx_manager,
            script_address=Address.from_primitive(oracle_addr),
            policy_id=ScriptHash.from_primitive(oracle_curr),
            reward_token_hash=(
                ScriptHash.from_primitive(reward_token_hash)
                if reward_token_hash
                else None
            ),
            reward_token_name=(
                AssetName.from_primitive(reward_token_name)
                if reward_token_name
                else None
            ),
        )

    async def handle_feed_request(
        self, oracle_nft_policy_id: str, tx_validity_interval: TxValidityInterval
    ) -> SignedOracleNodeMessage:
        """Handle ODV feed request"""
        try:
            timestamp = self.chain_query.get_current_posix_chain_time_ms()

            validate_timestamp(tx_validity_interval.model_dump(), timestamp)

            await validate_is_node_registered(
                self.tx_manager,
                self.oracle_addr,
                oracle_nft_policy_id,
                self.node_feed_vk.hash(),
            )

            # Get and process rate
            rate, _ = await self.rate_aggregator.fetch_aggregate_rates()
            if rate is None:
                raise RateAggregationError("Failed to get aggregated rate for ODV feed")

            # Create message
            message = OracleNodeMessage(
                feed=int(rate * 1_000_000),
                timestamp=timestamp,
                oracle_nft_policy_id=bytes.fromhex(oracle_nft_policy_id),
            )

            # Sign message and return signature
            signature = message.sign(self.node_feed_sk)

            signed_message = SignedOracleNodeMessage(
                message=message,
                signature=signature,
                verification_key=self.node_feed_vk,
            )
            return signed_message

        except (NodeServiceError, Exception) as e:
            logger.error(str(e))
            raise

    async def handle_aggregation_sign_request(
        self, node_values: dict[str, Any], tx_body_cbor_hex: str
    ) -> str:
        """Handle ODV aggregation transaction signing."""
        try:
            logger.info(
                f"Received transaction body CBOR length: {len(tx_body_cbor_hex)}"
            )

            tx_body_cbor_bytes = bytes.fromhex(tx_body_cbor_hex)
            tx_body_hash_bytes = hashlib.blake2b(
                tx_body_cbor_bytes, digest_size=32
            ).digest()
            tx_body_hash_hex = tx_body_hash_bytes.hex()

            logger.info(f"Computed transaction body hash: {tx_body_hash_hex}")

            # Deserialize transaction body for validation purposes only
            parsed_tx_body = TransactionBody.from_cbor(tx_body_cbor_hex)

            validation_tx = Transaction(
                transaction_body=parsed_tx_body,
                transaction_witness_set=TransactionWitnessSet(),
            )

            # Validates the node message signatures
            validated_node_messages = validate_node_message_signatures(
                [msg.model_dump() for msg in node_values.values()]
            )

            # Validate policy ID consistency
            validate_policy_id_in_messages(validated_node_messages)

            # Validates and returns the reward and agg transport datums
            reward_transport_datum, _ = validate_transaction_datums(
                validation_tx, self.oracle_addr
            )

            # Validates that the node updates and aggregation median are correct
            median_validation_passed = validate_node_updates_and_aggregation_median(
                validated_node_messages, reward_transport_datum.datum
            )

            if not median_validation_passed:
                raise ValidationError(
                    "Node updates and aggregation median validation failed"
                )

            logger.info("All validations passed successfully")

            # Sign the transaction body hash
            signature_bytes = self.node_feed_sk.sign(tx_body_hash_bytes)
            signature_hex = signature_bytes.hex()

            logger.info(
                f"Transaction signed successfully, signature length: {len(signature_hex)}"
            )

            return signature_hex

        except Exception as e:
            logger.error(f"Aggregation sign request failed: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Aggregation sign request failed: {str(e)}")
            raise

    async def attempt_reward_calculation(self, batch_size: int) -> None:
        """
        Build reward calculation tx and attempt submitting it,
        if the process fails there could be cases when we can be sure that it's normal:
        1. No pending transport utxos found
        2. Reward calculation was not subsidized (for batch sizes more than one we can wait for second pending transport and try again)
        3. Transaction submission error (can happen when e.g. utxo already consumed by other oracle node)
        4. Validation error: conditions for reward calculation have not been yet met
        """
        try:
            res = await self.odv_tx_builder.build_rewards_tx(
                signing_key=self.node_payment_sk,
                change_address=self.node_payment_addr,
                max_inputs=batch_size,
                check_if_tx_fee_subsidized=self.check_if_reward_calculation_fee_subsidized,
            )
            status, _ = await self.tx_manager.sign_and_submit(
                res.transaction,
                [self.node_payment_sk],
                wait_confirmation=True,
            )
            if status != "confirmed":
                logger.warning(f"Rewards calculation transaction failed: {status}")
            else:
                logger.info(
                    f"Rewards calculation transaction submitted: {res.transaction.id.payload.hex()}"
                )

        except NoPendingTransportUtxosFoundError as e:
            logger.info(str(e))
        except RewardCalculationIsNotSubsidizedError as e:
            logger.warning(
                f"Try submitting reward calculation without using subsidies: {e}"
            )
        except (TransactionError, ValidationError) as e:
            logger.warning(f"Rewards calculation failed: {e}")
