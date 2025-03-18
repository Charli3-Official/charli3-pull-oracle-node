import logging
from typing import Any

from charli3_offchain_core.blockchain.chain_query import ChainQuery
from charli3_offchain_core.blockchain.transactions import TransactionManager
from charli3_offchain_core.models.base import TxValidityInterval
from charli3_offchain_core.models.message import (
    OracleNodeMessage,
    SignedOracleNodeMessage,
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
    PaymentExtendedSigningKey,
    PaymentVerificationKey,
    Transaction,
    TransactionWitnessSet,
    VerificationKeyWitness,
    ExtendedSigningKey,
    VerificationKey,
)

from .aggregator import RateAggregator
from .errors import NodeServiceError, RateAggregationError, ValidationError

logger = logging.getLogger(__name__)


class OdvService:
    """Service handling ODV (On-Demand Validation) operations"""

    def __init__(
        self,
        rate_aggregator: RateAggregator,
        chain_query: ChainQuery,
        tx_manager: TransactionManager,
        oracle_addr: str,
        node_feed_sk: ExtendedSigningKey,
        node_feed_vk: VerificationKey,
        node_payment_sk: PaymentExtendedSigningKey,
        node_payment_vk: PaymentVerificationKey,
    ):
        self.rate_aggregator = rate_aggregator
        self.chain_query = chain_query
        self.tx_manager = tx_manager
        self.oracle_addr = oracle_addr
        self.node_feed_sk = node_feed_sk
        self.node_feed_vk = node_feed_vk
        self.node_payment_sk = node_payment_sk
        self.node_payment_vk = node_payment_vk

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
            rate, _ = await self.rate_aggregator.fetch_all_rates()
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
        self, node_values: dict[str, Any], tx_cbor: str
    ) -> str:
        """Handle ODV aggregation transaction signing."""
        try:
            tx = Transaction.from_cbor(tx_cbor)

            # Validates the node message signatures
            node_messages = validate_node_message_signatures(
                [msg.model_dump() for msg in node_values.values()]
            )
            # Validates that all messages have the same policy_id
            validate_policy_id_in_messages(node_messages)

            # Validates and returns the reward and agg transport datums
            reward_transport_datum, _ = validate_transaction_datums(
                tx, self.oracle_addr
            )

            # Validates that the node updates and aggregation median are correct
            if validate_node_updates_and_aggregation_median(
                node_messages, reward_transport_datum.datum
            ):
                witness = VerificationKeyWitness(
                    vkey=self.node_feed_vk,
                    signature=self.node_feed_sk.sign(tx.transaction_body.hash()),
                )
                tx.transaction_witness_set = (
                    tx.transaction_witness_set or TransactionWitnessSet()
                )
                tx.transaction_witness_set.vkey_witnesses.append(witness)

                return tx.to_cbor_hex()
            else:
                raise

        except (NodeServiceError, ValidationError, Exception) as e:
            logger.error(f"Aggregation sign request failed: {str(e)}")
            raise
