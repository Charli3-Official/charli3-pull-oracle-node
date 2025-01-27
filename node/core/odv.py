import logging

from api.schemas.node import (
    NodeAggregationSignRequest,
    NodeAggregationSignResponse,
    NodeFeedRequest,
    NodeFeedResponse,
)
from charli3_offchain_core.blockchain.chain_query import ChainQuery
from charli3_offchain_core.blockchain.transactions import TransactionManager
from charli3_offchain_core.models.node_types import (
    OracleNodeMessage,
    SignedOracleNodeMessage,
)
from pycardano import (
    PaymentExtendedSigningKey,
    PaymentVerificationKey,
    Transaction,
    TransactionWitnessSet,
    VerificationKeyHash,
    VerificationKeyWitness,
)

from .aggregator import RateAggregator
from .errors import NodeServiceError, RateAggregationError
from .validations import (
    get_current_timestamp,
    validate_node_registration,
    validate_timestamp,
)

logger = logging.getLogger(__name__)


class OdvService:
    """Service handling ODV (On-Demand Validation) operations"""

    def __init__(
        self,
        rate_aggregator: RateAggregator,
        chain_query: ChainQuery,
        tx_manager: TransactionManager,
        oracle_addr: str,
        node_sk: PaymentExtendedSigningKey,
        node_vk: PaymentVerificationKey,
        node_vkh: VerificationKeyHash,
    ):
        self.rate_aggregator = rate_aggregator
        self.chain_query = chain_query
        self.tx_manager = tx_manager
        self.oracle_addr = oracle_addr
        self.node_sk = node_sk
        self.node_vk = node_vk
        self.node_vkh = node_vkh.to_primitive().hex()

    async def handle_feed_request(self, request: NodeFeedRequest) -> NodeFeedResponse:
        """Handle ODV feed request"""
        try:
            timestamp = get_current_timestamp()

            validate_timestamp(request.tx_validity_interval.model_dump(), timestamp)

            await validate_node_registration(
                self.tx_manager,
                self.oracle_addr,
                self.node_vk,
                request.oracle_nft_policy_id,
            )

            # Get and process rate
            rate, _ = await self.rate_aggregator.fetch_all_rates()
            if rate is None:
                raise RateAggregationError("Failed to get aggregated rate for ODV feed")

            # Create message
            message = OracleNodeMessage(
                feed=int(rate * 1_000_000),
                timestamp=timestamp,
                oracle_nft_policy_id=bytes.fromhex(request.oracle_nft_policy_id),
            )

            # Sign message and return signature
            signature = message.sign(self.node_sk)

            return SignedOracleNodeMessage(
                message=message,
                verification_key=self.node_vk,
                signature=signature,
            ).to_json()

        except (NodeServiceError, Exception) as e:
            logger.error(str(e))
            raise

    async def handle_aggregation_sign_request(
        self, request: NodeAggregationSignRequest
    ) -> NodeAggregationSignResponse:
        """Handle ODV aggregation transaction signing"""
        try:
            for vkey_hex, data in request.nodes_messages.items():
                signed_message = SignedOracleNodeMessage.from_json(data)

                if not signed_message.validate():
                    raise ValueError(f"Invalid signature for node {vkey_hex}")

            tx = Transaction.from_cbor(request.tx_cbor)
            witness = VerificationKeyWitness(
                vkey=self.node_vk,
                signature=self.node_sk.sign(tx.transaction_body.hash()),
            )

            if tx.transaction_witness_set is None:
                tx.transaction_witness_set = TransactionWitnessSet()
            tx.transaction_witness_set.vkey_witnesses.append(witness)

            return NodeAggregationSignResponse(signed_tx_cbor=tx.to_cbor_hex())

        except (NodeServiceError, Exception) as e:
            logger.error(str(e))
            raise
