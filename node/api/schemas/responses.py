from typing import Any

from pydantic import BaseModel, Field


class SourceBreakdown(BaseModel):
    """Per-source price contribution to the final feed value."""

    source: str = Field(..., description="Name of the data source/provider")
    price: float = Field(
        ..., description="Price reported by this source (post quote-conversion)"
    )
    timestamp: float = Field(
        ..., description="Unix timestamp of when the price was fetched"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata, e.g. original_price, quote_rate",
    )


class NodeFeedResponse(BaseModel):
    """Response containing signed feed value."""

    message: str = Field(..., description="Signed feed message CBOR hex")
    signature: str = Field(..., description="Signature hex")
    verification_key: str = Field(..., description="Verification key hex")
    source_breakdown: list[SourceBreakdown] = Field(
        default_factory=list,
        description="Per-source price breakdown used to derive the final aggregated feed value. Off-chain only — not included in the signed on-chain message.",
    )


class NodeAggregationSignResponse(BaseModel):
    """Response containing signature"""

    signature: str = Field(..., description="Transaction signature hex")
