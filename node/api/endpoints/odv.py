"""ODV protocol endpoints."""

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from node.api.dependencies import get_odv_service
from node.api.schemas.requests import NodeAggregationSignRequest, NodeFeedRequest
from node.api.schemas.responses import NodeAggregationSignResponse, NodeFeedResponse
from node.background_tasks import run_reward_calculation_handler
from node.config.models import AppConfig
from node.core.errors import NodeServiceError
from node.core.odv import OdvService

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
        response = await odv_service.handle_feed_request(
            request.oracle_nft_policy_id, request.tx_validity_interval
        )
        return NodeFeedResponse.model_validate(response.model_dump())
    except NodeServiceError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "detail": str(e),
                "error_code": e.status_code,
                "error_type": e.__class__.__name__,
            },
        )


@router.post("/sign", response_model=NodeAggregationSignResponse)
async def sign_aggregation(
    background_tasks: BackgroundTasks,
    request: Request,
    signature_request: NodeAggregationSignRequest,
    odv_service: OdvService = Depends(get_odv_service),
):
    """Handle ODV aggregation transaction signing."""
    try:
        signature_hex = await odv_service.handle_aggregation_sign_request(
            signature_request.node_messages, signature_request.tx_body_cbor
        )
        app_config: AppConfig | None = request.state.app_config
        assert app_config, "App config is not set up!"
        lock_for_reward_calculator: asyncio.Lock | None = (
            request.state.lock_for_reward_calculator
        )
        assert lock_for_reward_calculator, "Reward calculator lock is not set up!"

        background_tasks.add_task(
            run_reward_calculation_handler,
            app_config.updater,
            odv_service,
            lock_for_reward_calculator,
        )

        return NodeAggregationSignResponse(signature=signature_hex)
    except NodeServiceError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "detail": str(e),
                "error_code": e.status_code,
                "error_type": e.__class__.__name__,
            },
        )
