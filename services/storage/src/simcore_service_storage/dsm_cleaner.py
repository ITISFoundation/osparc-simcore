"""background task that periodically cleans up the DSM of expired uploads and exporter archives.

For details see `SimcoreS3DataManager`:
    - `.clean_expired_uploads()`
    - `.clean_expired_exports()`
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import cast

from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_context
from servicelib.tracing import traced
from settings_library.redis import RedisDatabase

from .core.settings import get_application_settings
from .dsm import get_dsm_provider
from .modules.redis import get_redis_client_manager
from .simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)

_TASK_NAME_PERIODICALLY_CLEAN_DSM = "periodic_cleanup_of_dsm_uploads"
_TASK_NAME_PERIODICALLY_CLEAN_EXPORTS = "periodic_cleanup_exports"


def _get_simcore_s3_dsm(app: FastAPI) -> SimcoreS3DataManager:
    dsm = get_dsm_provider(app)
    return cast(SimcoreS3DataManager, dsm.get(SimcoreS3DataManager.get_location_id()))


@traced
async def dsm_cleaner_task(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "dsm cleaner task"):
        await _get_simcore_s3_dsm(app).clean_expired_uploads()


@traced
async def dsm_export_cleaner_task(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "export cleaner task"):
        await _get_simcore_s3_dsm(app).clean_expired_exports()


@asynccontextmanager
async def _dsm_cleaner_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for DSM cleaner."""
    app.state.dsm_cleaner_task = None
    app.state.dsm_export_cleaner_task = None

    try:
        cfg = get_application_settings(app)
        lock_client = get_redis_client_manager(app).client(RedisDatabase.LOCKS)

        if cfg.STORAGE_CLEANER_INTERVAL_S:

            @exclusive_periodic(
                lock_client,
                task_interval=timedelta(seconds=cfg.STORAGE_CLEANER_INTERVAL_S),
                retry_after=timedelta(minutes=5),
            )
            async def _periodic_dsm_clean() -> None:
                await dsm_cleaner_task(app)

            app.state.dsm_cleaner_task = asyncio.create_task(
                _periodic_dsm_clean(), name=_TASK_NAME_PERIODICALLY_CLEAN_DSM
            )

        if cfg.STORAGE_EXPORT_CLEANER_INTERVAL:

            @exclusive_periodic(
                lock_client,
                task_interval=cfg.STORAGE_EXPORT_CLEANER_INTERVAL,
                retry_after=timedelta(minutes=5),
            )
            async def _periodic_dsm_export_clean() -> None:
                await dsm_export_cleaner_task(app)

            app.state.dsm_export_cleaner_task = asyncio.create_task(
                _periodic_dsm_export_clean(), name=_TASK_NAME_PERIODICALLY_CLEAN_EXPORTS
            )

        yield
    finally:
        for task in (app.state.dsm_cleaner_task, app.state.dsm_export_cleaner_task):
            if isinstance(task, asyncio.Task):
                await cancel_wait_task(task)


def configure_dsm_cleaner(app_lifespan: LifespanManager) -> None:
    """Configure DSM cleaner lifespan."""
    app_lifespan.add(_dsm_cleaner_lifespan)
