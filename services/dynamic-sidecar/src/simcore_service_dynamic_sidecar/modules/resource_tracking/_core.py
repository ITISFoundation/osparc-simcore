import logging

from fastapi import FastAPI

_logger = logging.getLogger(__name__)


async def send_service_stopped(app: FastAPI) -> None:
    _logger.debug("TODO: send service stopped")


async def send_service_started(app: FastAPI) -> None:
    _logger.debug("TODO: send service started")


async def heart_beat_task(app: FastAPI):
    _logger.debug("TODO: send service heart beat")
