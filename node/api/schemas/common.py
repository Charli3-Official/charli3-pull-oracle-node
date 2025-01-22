from pydantic import BaseModel, Field


class TxValidityInterval(BaseModel):
    """Transaction validity interval model"""

    start: int = Field(..., description="Start timestamp in milliseconds")
    end: int = Field(..., description="End timestamp in milliseconds")
