import asyncio
import logging
from asyncio import AbstractEventLoop

from celery import current_app
from fastapi import FastAPI
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID

_logger = logging.getLogger(__name__)


def get_fastapi_app():
    fast_api_app: FastAPI = current_app.conf.fastapi_app
    return fast_api_app


def get_loop() -> AbstractEventLoop:  # nosec
    loop: AbstractEventLoop = current_app.conf.loop
    return loop


async def _async_archive(user_id: UserID, files: list[StorageFileID]) -> None:
    fast_api_app: FastAPI = get_fastapi_app()

    _logger.error(
        "Archiving: %s (%s, %s)", ", ".join(files), f"{user_id=}", f"{fast_api_app=}"
    )


def archive(user_id: UserID, files: list[StorageFileID]) -> None:
    asyncio.run_coroutine_threadsafe(_async_archive(user_id, files), get_loop())
