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
import os
import socket
from contextlib import suppress
from typing import cast

from aiohttp import web

from .constants import APP_CONFIG_KEY, APP_DSM_KEY
from .dsm_factory import DataManagerProvider
from .settings import Settings
from .simcore_s3_dsm import SimcoreS3DataManager

logger = logging.getLogger(__name__)


async def dsm_cleaner_task(app: web.Application) -> None:
    logger.info("starting dsm cleaner task...")
    cfg: Settings = app[APP_CONFIG_KEY]
    dsm: DataManagerProvider = app[APP_DSM_KEY]
    simcore_s3_dsm: SimcoreS3DataManager = cast(
        SimcoreS3DataManager, dsm.get(SimcoreS3DataManager.get_location_id())
    )
    assert cfg.STORAGE_CLEANER_INTERVAL_S  # nosec
    while await asyncio.sleep(cfg.STORAGE_CLEANER_INTERVAL_S, result=True):
        try:
            await simcore_s3_dsm.clean_expired_uploads()

        except asyncio.CancelledError:  # noqa: PERF203
            logger.info("cancelled dsm cleaner task")
            raise
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unhandled error in dsm cleaner task, restarting task...")


def setup_dsm_cleaner(app: web.Application):
    async def _setup(app: web.Application):
        task = asyncio.create_task(
            dsm_cleaner_task(app),
            name=f"dsm_cleaner_task_{socket.gethostname()}_{os.getpid()}",
        )
        logger.info("%s created", f"{task=}")

        yield

        logger.debug("stopping %s...", f"{task=}")
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        logger.info("%s stopped.", f"{task=}")

    app.cleanup_ctx.append(_setup)
