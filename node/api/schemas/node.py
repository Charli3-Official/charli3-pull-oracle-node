from typing import Any

from pydantic import BaseModel, Field


class NodeFeedRequest(BaseModel):
    """Request for oracle feed value"""

    oracle_nft_policy_id: str = Field(..., description="Oracle NFT policy ID")
    tx_validity_interval: dict[str, int] = Field(
        ..., description="Transaction validity interval {start: int, end: int}"
    )


class NodeFeedResponse(BaseModel):
    """Response containing signed feed value"""

    feed: str = Field(..., description="Oracle feed value")
    timestamp: int = Field(..., description="Feed timestamp")
    verification_key: str = Field(..., description="Node's verification key hex")
    signature: str = Field(..., description="ed25519 signature hex")


class NodeAggregationSignRequest(BaseModel):
    """Request to sign transaction"""

    nodes_messages: dict[str, Any] = Field(..., description="Collected node messages")
    tx_cbor: str = Field(..., description="Transaction CBOR hex")


class NodeAggregationSignResponse(BaseModel):
    """Response containing signed transaction"""

    signed_tx_cbor: str = Field(..., description="Signed transaction CBOR hex")
