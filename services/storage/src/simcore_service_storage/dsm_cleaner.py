"""backround task that cleans the DSM pending/expired uploads

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

from common_library.async_tools import cancel_and_wait
from fastapi import FastAPI
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_context

from .core.settings import get_application_settings
from .dsm import get_dsm_provider
from .modules.redis import get_redis_client
from .simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)

_TASK_NAME_PERIODICALY_CLEAN_DSM = "periodic_cleanup_of_dsm"


async def dsm_cleaner_task(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "dsm cleaner task"):
        dsm = get_dsm_provider(app)
        simcore_s3_dsm: SimcoreS3DataManager = cast(
            SimcoreS3DataManager, dsm.get(SimcoreS3DataManager.get_location_id())
        )
        await simcore_s3_dsm.clean_expired_uploads()


def setup_dsm_cleaner(app: FastAPI) -> None:
    async def _on_startup() -> None:
        cfg = get_application_settings(app)
        assert cfg.STORAGE_CLEANER_INTERVAL_S  # nosec

        @exclusive_periodic(
            get_redis_client(app),
            task_interval=timedelta(seconds=cfg.STORAGE_CLEANER_INTERVAL_S),
            retry_after=timedelta(minutes=5),
        )
        async def _periodic_dsm_clean() -> None:
            await dsm_cleaner_task(app)

        app.state.dsm_cleaner_task = asyncio.create_task(
            _periodic_dsm_clean(), name=_TASK_NAME_PERIODICALY_CLEAN_DSM
        )

    async def _on_shutdown() -> None:
        assert isinstance(app.state.dsm_cleaner_task, asyncio.Task)  # nosec
        await cancel_and_wait(app.state.dsm_cleaner_task)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
