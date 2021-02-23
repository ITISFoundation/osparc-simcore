# Used to save and restore service state

import logging
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

state_router = APIRouter()


@state_router.get("/state")
async def asd1(request: Request) -> str:
    logger.warning("TODO: still need to implement state saving")
    return ""


@state_router.post("/state")
async def asd_endpoint(request: Request) -> str:
    logger.warning("TODO: still need to implement state saving")
    return ""


__all__ = ["state_router"]
