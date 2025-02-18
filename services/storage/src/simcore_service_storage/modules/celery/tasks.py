import asyncio
import logging
from asyncio import AbstractEventLoop

from celery import Task
from fastapi import FastAPI
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID

from .worker.main import celery_app

_logger = logging.getLogger(__name__)


def get_fastapi_app(celery_app):
    fast_api_app: FastAPI = celery_app.conf.get("fastapi_app")
    return fast_api_app


def get_loop(celery_app) -> AbstractEventLoop:  # nosec
    loop: AbstractEventLoop = celery_app.conf.get("loop")
    return loop


async def _async_archive(
    celery_app, user_id: UserID, files: list[StorageFileID]
) -> StorageFileID:
    fast_api_app: FastAPI = get_fastapi_app(celery_app)

    _logger.debug(
        "Archiving: %s (%s, %s)", ", ".join(files), f"{user_id=}", f"{fast_api_app=}"
    )

    return "_".join(files) + ".zip"


@celery_app.task(name="archive", bind=True)
def archive(task: Task, user_id: UserID, files: list[StorageFileID]) -> StorageFileID:
    return asyncio.run_coroutine_threadsafe(
        _async_archive(task.app, user_id, files), get_loop(task.app)
    ).result()
