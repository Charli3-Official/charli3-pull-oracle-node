import hashlib
import logging
from typing import Any

import charli3_offchain_core.oracle.aggregate.builder as odv_builder
from charli3_offchain_core.blockchain.chain_query import ChainQuery
from charli3_offchain_core.blockchain.transactions import TransactionManager
from charli3_offchain_core.cli.base import LoadedKeys
from charli3_offchain_core.models.base import TxValidityInterval
from charli3_offchain_core.models.message import (
    OracleNodeMessage,
    SignedOracleNodeMessage,
)
from charli3_offchain_core.models.oracle_datums import NoDatum, SomeAsset
from charli3_offchain_core.oracle.exceptions import (
    AggregationError,
    DataError,
    NFTError,
    NodeValidationError,
    SignatureError,
    StateValidationError,
    TimestampError,
)
from charli3_offchain_core.oracle.rewards.node_collect_builder import NodeCollectBuilder
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
    VerificationKeyHash,
)

from node.core.aggregator import RateAggregator
from node.core.errors import NodeServiceError, RateAggregationError, ValidationError
from node.services.cli_automation import create_reward_collection_automation

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
        node_feed_vkh: VerificationKeyHash,
        node_payment_sk: PaymentExtendedSigningKey,
        node_payment_vk: PaymentVerificationKey,
        reward_token_hash: str | None = None,
        reward_token_name: str | None = None,
        reward_destination_address: str | None = None,
        create_collateral: bool = True,
        check_if_reward_calculation_fee_subsidized: bool = False,
    ):
        self.rate_aggregator = rate_aggregator
        self.chain_query = chain_query
        self.tx_manager = tx_manager
        self.oracle_addr = oracle_addr
        self.oracle_curr = oracle_curr
        self.reward_token_hash = reward_token_hash
        self.reward_token_name = reward_token_name
        self.reward_destination_address = reward_destination_address
        self.create_collateral = create_collateral
        self.check_if_reward_calculation_fee_subsidized = (
            check_if_reward_calculation_fee_subsidized
        )
        self.node_feed_sk = node_feed_sk
        self.node_feed_vk = node_feed_vk
        self.node_feed_vkh = node_feed_vkh
        self.node_payment_sk = node_payment_sk
        self.node_payment_vk = node_payment_vk
        self.network = self.chain_query.context.network
        self.node_payment_addr = Address(
            payment_part=self.node_payment_vk.hash(), network=self.network
        )

        self.oracle_script_address = Address.from_primitive(oracle_addr)
        self.oracle_policy_id = ScriptHash.from_primitive(oracle_curr)
        self.reward_token_policy_hash = (
            ScriptHash.from_primitive(reward_token_hash) if reward_token_hash else None
        )
        self.reward_token_asset_name = (
            AssetName.from_primitive(reward_token_name) if reward_token_name else None
        )

        self.odv_tx_builder = odv_builder.OracleTransactionBuilder(
            tx_manager=self.tx_manager,
            script_address=self.oracle_script_address,
            policy_id=self.oracle_policy_id,
            reward_token_hash=self.reward_token_policy_hash,
            reward_token_name=self.reward_token_asset_name,
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

            tx_body_cbor_bytes = bytes.fromhex(tx_body_cbor_hex)
            tx_body_hash_bytes = hashlib.blake2b(
                tx_body_cbor_bytes, digest_size=32
            ).digest()
            # tx_body_hash_hex = tx_body_hash_bytes.hex()

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

            # Validate and extract required datums from the transaction.
            reward_account_datum, agg_state_datum = validate_transaction_datums(
                validation_tx, self.oracle_addr
            )

            # Validate median using AggState datum
            median_validation_passed = validate_node_updates_and_aggregation_median(
                validated_node_messages, agg_state_datum
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
                f"Transaction signed successfully with signature: {signature_hex}"
            )

            return signature_hex

        except (
            SignatureError,
            NFTError,
            DataError,
            AggregationError,
            NodeValidationError,
            StateValidationError,
            TimestampError,
        ) as e:
            logger.warning(f"Validation failed during aggregation signing: {e}")
            raise ValidationError(str(e)) from e
        except Exception as e:
            logger.error(f"Aggregation sign request failed: {str(e)}")
            raise

    async def attempt_node_collect(self, contract_utxos: list | None = None) -> None:
        """
        Build node collect tx and attempt submitting it,
        if the process fails there could be cases when we can be sure that it's normal:
        1. No rewards available for the node
        2. Transaction submission error (can happen when e.g. utxo already consumed by other node)
        3. Validation error: conditions for node collect have not been yet met
        """
        try:
            if contract_utxos is None:
                return

            loaded_keys = LoadedKeys(
                payment_sk=self.node_payment_sk,
                payment_vk=self.node_feed_vk,
                stake_vk=self.node_payment_vk,
                address=self.node_payment_addr,
            )

            # Create NodeCollectBuilder and build the transaction
            node_collect_builder = NodeCollectBuilder(self.chain_query, self.tx_manager)

            # Use automated prompts if configured
            if self.reward_destination_address:
                # Create automation service for reward collection
                automation_service = create_reward_collection_automation(
                    create_collateral=self.create_collateral,
                    reward_destination=self.reward_destination_address,
                )

                with automation_service.automate_prompts():
                    result = await node_collect_builder.build_tx(
                        policy_hash=self.oracle_policy_id,
                        contract_utxos=contract_utxos,
                        reward_token=(
                            SomeAsset(
                                policy_id=self.reward_token_policy_hash,
                                asset_name=self.reward_token_asset_name,
                            )
                            if self.reward_token_policy_hash
                            and self.reward_token_asset_name
                            else NoDatum()
                        ),
                        loaded_key=loaded_keys,
                        network=self.network,
                        required_signers=[
                            self.node_feed_vk.hash(),
                            self.node_payment_vk.hash(),
                        ],
                    )

                # Check if transaction was built successfully
                if result.exception_type is not None:
                    logger.warning(
                        f"Node collect transaction build failed: {result.exception_type}"
                    )
                    return

                if result.transaction is None:
                    logger.warning(
                        "Node collect transaction build returned no transaction"
                    )
                    return

                # Submit the transaction
                status, _ = await self.tx_manager.sign_and_submit(
                    result.transaction,
                    [self.node_feed_sk, self.node_payment_sk],
                    wait_confirmation=True,
                )
                if status != "confirmed":
                    logger.warning(f"Node collect transaction failed: {status}")
                else:
                    logger.info(
                        f"Node collect transaction submitted: {result.transaction.id.payload.hex()}"
                    )

        except Exception as e:
            logger.warning(f"Node collect failed: {e}")
