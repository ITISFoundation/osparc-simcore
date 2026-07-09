"""background task that periodically cleans up the DSM of expired uploads and exporter archives.

For details see `SimcoreS3DataManager`:
    - `.clean_expired_uploads()`
    - `.clean_expired_exports()`
"""

import asyncio
import logging
from asyncio import create_task
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import cast

from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_catch, log_context
from servicelib.tracing import traced
from settings_library.redis import RedisDatabase

from .core.settings import get_application_settings
from .dsm import get_dsm_provider
from .modules.redis import get_redis_client_manager
from .simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)

_TASK_NAME_CLEAN_EXPIRED_UPLOADS = "clean_expired_uploads"
_TASK_NAME_CLEAN_EXPIRED_EXPORTS = "clean_expired_exports"


def _get_simcore_s3_dsm(app: FastAPI) -> SimcoreS3DataManager:
    dsm = get_dsm_provider(app)
    return cast(SimcoreS3DataManager, dsm.get(SimcoreS3DataManager.get_location_id()))


@traced
async def clean_expired_uploads(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "clean expired uploads"):
        await _get_simcore_s3_dsm(app).clean_expired_uploads()


@traced
async def clean_expired_exports(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "clean expired exports"):
        await _get_simcore_s3_dsm(app).clean_expired_exports()


@asynccontextmanager
async def _dsm_cleaner_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    tasks_to_stop: list[asyncio.Task] = []
    try:
        cfg = get_application_settings(app)
        lock_client = get_redis_client_manager(app).client(RedisDatabase.LOCKS)

        @exclusive_periodic(
            lock_client,
            task_interval=cfg.STORAGE_CLEANER.STORAGE_CLEANER_EXPIRE_UPLOADS_INTERVAL,
            retry_after=timedelta(minutes=5),
        )
        async def _run_clean_expired_uploads() -> None:
            await clean_expired_uploads(app)

        tasks_to_stop.append(create_task(_run_clean_expired_uploads(), name=_TASK_NAME_CLEAN_EXPIRED_UPLOADS))

        @exclusive_periodic(
            lock_client,
            task_interval=cfg.STORAGE_CLEANER.STORAGE_CLEANER_EXPORT_INTERVAL,
            retry_after=timedelta(minutes=5),
        )
        async def _run_clean_expired_exports() -> None:
            await clean_expired_exports(app)

        tasks_to_stop.append(create_task(_run_clean_expired_exports(), name=_TASK_NAME_CLEAN_EXPIRED_EXPORTS))

        yield
    finally:
        for task in tasks_to_stop:
            with log_catch(_logger):
                await cancel_wait_task(task)


def configure_dsm_cleaner(app_lifespan: LifespanManager) -> None:
    app_lifespan.add(_dsm_cleaner_lifespan)
