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

_TASK_NAME_PERIODICALLY_CLEAN_DSM = "periodic_cleanup_of_dsm"


@traced
async def dsm_cleaner_task(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "dsm cleaner task"):
        dsm = get_dsm_provider(app)
        simcore_s3_dsm: SimcoreS3DataManager = cast(
            SimcoreS3DataManager, dsm.get(SimcoreS3DataManager.get_location_id())
        )
        await simcore_s3_dsm.clean_expired_uploads()
        await simcore_s3_dsm.clean_expired_exports()


@asynccontextmanager
async def _dsm_cleaner_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for DSM cleaner."""
    app.state.dsm_cleaner_task = None

    try:
        cfg = get_application_settings(app)
        assert cfg.STORAGE_CLEANER_INTERVAL_S  # nosec

        @exclusive_periodic(
            get_redis_client_manager(app).client(RedisDatabase.LOCKS),
            task_interval=timedelta(seconds=cfg.STORAGE_CLEANER_INTERVAL_S),
            retry_after=timedelta(minutes=5),
        )
        async def _periodic_dsm_clean() -> None:
            await dsm_cleaner_task(app)

        app.state.dsm_cleaner_task = asyncio.create_task(_periodic_dsm_clean(), name=_TASK_NAME_PERIODICALLY_CLEAN_DSM)

        yield
    finally:
        if isinstance(app.state.dsm_cleaner_task, asyncio.Task):
            await cancel_wait_task(app.state.dsm_cleaner_task)


def configure_dsm_cleaner(app_lifespan: LifespanManager) -> None:
    """Configure DSM cleaner lifespan."""
    app_lifespan.add(_dsm_cleaner_lifespan)
