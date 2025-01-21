"""ODV protocol endpoints."""

from api.dependencies import get_odv_service
from api.schemas.node import (
    NodeAggregationSignRequest,
    NodeAggregationSignResponse,
    NodeFeedRequest,
    NodeFeedResponse,
)
from core.errors import NodeServiceError
from core.odv import OdvService
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post(
    "/feed",
    response_model=NodeFeedResponse,
)
async def get_feed(
    request: NodeFeedRequest, odv_service: OdvService = Depends(get_odv_service)
):
    """Handle ODV feed value request."""
    try:
        return await odv_service.handle_feed_request(request)
    except NodeServiceError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "detail": str(e),
                "error_code": e.status_code,
                "error_type": e.__class__.__name__,
            },
        )


@router.post("/aggregation/sign", response_model=NodeAggregationSignResponse)
async def sign_aggregation(
    request: NodeAggregationSignRequest,
    odv_service: OdvService = Depends(get_odv_service),
):
    """Handle ODV aggregation transaction signing."""
    try:
        return await odv_service.handle_aggregation_sign_request(request)
    except NodeServiceError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "detail": str(e),
                "error_code": e.status_code,
                "error_type": e.__class__.__name__,
            },
        )
