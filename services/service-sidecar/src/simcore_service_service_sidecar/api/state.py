# acts as mock for now

import logging
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

state_router = APIRouter()


@state_router.get("/state")
async def get_api(request: Request) -> str:
    logger.warning("TODO: still need to implement")
    return ""


@state_router.post("/state")
async def post_api(request: Request) -> str:
    logger.warning("TODO: still need to implement")
    return ""


__all__ = ["state_router"]
