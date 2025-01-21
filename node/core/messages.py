from dataclasses import dataclass
from typing import Optional

from charli3_offchain_core.oracle.utils.signature_checks import encode_oracle_feed
from pycardano import PaymentExtendedSigningKey, Transaction

from .errors import MessageCreationError, MessageSigningError, TransactionSigningError


@dataclass
class OdvFeedMessage:
    """Message containing oracle feed data for ODV"""

    feed_value: int
    timestamp: int
    policy_id: str
    signature: Optional[str] = None

    def to_encode(self) -> bytes:
        """Convert feed message to CBOR format"""
        try:
            return encode_oracle_feed(self.feed_value, self.timestamp)
        except Exception as e:
            raise MessageCreationError(f"Failed to encode ODV feed message: {str(e)}")

    def sign(self, signing_key: PaymentExtendedSigningKey) -> "OdvFeedMessage":
        """Sign feed message and return new instance"""
        try:
            signature = signing_key.sign(self.to_encode()).hex()
            return OdvFeedMessage(
                feed_value=self.feed_value,
                timestamp=self.timestamp,
                policy_id=self.policy_id,
                signature=signature,
            )
        except Exception as e:
            raise MessageSigningError(f"Failed to sign ODV feed message: {str(e)}")


@dataclass
class OdvAggregationMessage:
    """Message for ODV transaction aggregation"""

    tx_cbor: str
    nodes_messages: dict[str, str]

    def decode_transaction(self) -> Transaction:
        """Decode CBOR into Transaction"""
        try:
            tx = Transaction.from_cbor(self.tx_cbor)
            if not isinstance(tx, Transaction):
                raise MessageCreationError("Invalid ODV aggregation transaction format")
            return tx
        except Exception as e:
            raise MessageCreationError(
                f"Failed to decode ODV aggregation transaction: {str(e)}"
            )

    def sign(self, signing_key: PaymentExtendedSigningKey) -> bytes:
        """Sign aggregation transaction"""
        try:
            tx = self.decode_transaction()
            return signing_key.sign(tx.transaction_body.hash())
        except Exception as e:
            raise TransactionSigningError(
                f"Failed to sign ODV aggregation transaction: {str(e)}"
            )
