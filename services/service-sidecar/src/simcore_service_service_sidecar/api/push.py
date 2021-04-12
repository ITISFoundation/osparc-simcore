# acts as mock for now

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

push_router = APIRouter()


@push_router.post("/push")
async def post_api(request: Request) -> str:
    logger.warning("TODO: still need to implement")
    return ""


__all__ = ["push_router"]
