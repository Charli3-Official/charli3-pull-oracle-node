from pydantic import BaseModel, Field


class NodeFeedResponse(BaseModel):
    """Response containing signed feed value."""

    message: str = Field(..., description="Signed feed message CBOR hex")
    signature: str = Field(..., description="Signature hex")
    verification_key: str = Field(..., description="Verification key hex")


class NodeAggregationSignResponse(BaseModel):
    """Response containing signature"""

    signature: str = Field(..., description="Transaction signature hex")
