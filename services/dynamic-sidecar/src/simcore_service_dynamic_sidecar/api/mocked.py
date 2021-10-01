"""
All the functions is this module are mocked out
because they are called by the frontend.
Avoids raising errors in the service.
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

mocked_router = APIRouter(tags=["Mocked frontend calls"])


@mocked_router.post("/push")
async def ignored_push_post() -> str:
    logger.warning("ignoring call POST /push from frontend")
    return ""


@mocked_router.get("/retrieve")
async def ignored_port_data_load() -> str:
    logger.warning("ignoring call GET /retrieve from frontend")
    return ""


@mocked_router.post("/retrieve")
async def ignored_port_data_save() -> str:
    logger.warning("ignoring call POST /retrieve from frontend")
    return ""


@mocked_router.get("/state")
async def ignored_load_service_state_state() -> str:
    logger.warning("ignoring call GET /state from frontend")
    return ""


@mocked_router.post("/state")
async def ignored_save_service_state_state() -> str:
    logger.warning("ignoring call POST /state from frontend")
    return ""


__all__ = ["mocked_router"]
