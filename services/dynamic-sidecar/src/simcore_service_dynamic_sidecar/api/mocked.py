"""
All the functions is this module are mocked out 
because they are called by the frontend.
Avoids raising errors in the service.
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

mocked_router = APIRouter()


@mocked_router.post("/push")
async def post_push() -> str:
    logger.warning("TODO: still need to implement")
    return ""


@mocked_router.get("/retrive")
async def get_retrive() -> str:
    logger.warning("TODO: still need to implement")
    return ""


@mocked_router.post("/retrive")
async def post_retrive() -> str:
    logger.warning("TODO: still need to implement")
    return ""


@mocked_router.get("/state")
async def get_state() -> str:
    logger.warning("TODO: still need to implement")
    return ""


@mocked_router.post("/state")
async def post_state() -> str:
    logger.warning("TODO: still need to implement")
    return ""


__all__ = ["mocked_router"]
