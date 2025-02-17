import asyncio
import logging
from asyncio import AbstractEventLoop

from celery import current_app
from fastapi import FastAPI

_logger = logging.getLogger(__name__)


def get_fastapi_app() -> FastAPI:
    fast_api_app: FastAPI = current_app.conf.fastapi_app
    return fast_api_app


def get_loop() -> AbstractEventLoop:  # nosec
    loop: AbstractEventLoop = current_app.conf.loop
    return loop


async def _async_archive(files: list[str]) -> None:
    fast_api_app: FastAPI = get_fastapi_app()

    _logger.error("Archiving: %s (conf=%s)", ", ".join(files), f"{fast_api_app}")


def archive(files: list[str]) -> None:
    asyncio.run_coroutine_threadsafe(_async_archive(files), get_loop())
