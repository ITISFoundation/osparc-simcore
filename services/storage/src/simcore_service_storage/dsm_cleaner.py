""" backround task that cleans the DSM pending/expired uploads

# Rationale:
 - for each upload an entry is created in the file_meta_data table in the database
 - then an upload link (S3/HTTP URL) is created through S3 backend and sent back to the client
 - the client shall upload the file and then notify DSM of completion
 - upon completion the corresponding entry in file_meta_data is updated:
   - the file_size of the uploaded file is set
   - the upload_expiration_date is set to null
   - if the uploadId exists (for multipart uploads) it is set to null

# DSM cleaner:
 - runs at an interval
 - list the entries that are expired in the database by checking "upload_expires_at" column
 - tries to update from S3 the database first, if that fails:
   - removes the entries in the database that are expired:
      - removes the entry
      - aborts the multipart upload if any
"""

import asyncio
import logging
from datetime import timedelta
from typing import cast

from aiohttp import web
from servicelib.background_task import stop_periodic_task
from servicelib.logging_utils import log_catch, log_context
from servicelib.redis_utils import start_exclusive_periodic_task

from .constants import APP_CONFIG_KEY, APP_DSM_KEY
from .dsm_factory import DataManagerProvider
from .redis import get_redis_client
from .settings import Settings
from .simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)

_TASK_NAME_PERIODICALY_CLEAN_DSM = "periodic_cleanup_of_dsm"


async def dsm_cleaner_task(app: web.Application) -> None:
    _logger.info("starting dsm cleaner task...")
    dsm: DataManagerProvider = app[APP_DSM_KEY]
    simcore_s3_dsm: SimcoreS3DataManager = cast(
        SimcoreS3DataManager, dsm.get(SimcoreS3DataManager.get_location_id())
    )
    try:
        await simcore_s3_dsm.clean_expired_uploads()

    except asyncio.CancelledError:  # noqa: PERF203
        _logger.info("cancelled dsm cleaner task")
        raise
    except Exception:  # pylint: disable=broad-except
        _logger.exception("Unhandled error in dsm cleaner task, restarting task...")


def setup_dsm_cleaner(app: web.Application):
    async def _setup(app: web.Application):
        with log_context(_logger, logging.INFO, msg="setup dsm cleaner"), log_catch(
            _logger, reraise=False
        ):
            cfg: Settings = app[APP_CONFIG_KEY]
            assert cfg.STORAGE_CLEANER_INTERVAL_S  # nosec

            storage_background_task = start_exclusive_periodic_task(
                get_redis_client(app),
                dsm_cleaner_task,
                task_period=timedelta(seconds=cfg.STORAGE_CLEANER_INTERVAL_S),
                retry_after=timedelta(minutes=5),
                task_name=_TASK_NAME_PERIODICALY_CLEAN_DSM,
                app=app,
            )

            yield

            await stop_periodic_task(storage_background_task)

    app.cleanup_ctx.append(_setup)
