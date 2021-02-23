# acts as mock for now

import logging
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

retrive_router = APIRouter()


@retrive_router.get("/retrive")
async def get_api(request: Request) -> str:
    logger.warning("TODO: still need to implement")
    return ""


@retrive_router.post("/retrive")
async def post_api(request: Request) -> str:
    logger.warning("TODO: still need to implement")
    return ""


__all__ = ["retrive_router"]
