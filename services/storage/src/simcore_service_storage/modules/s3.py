"""Module to access s3 service"""

import logging
from collections.abc import AsyncGenerator
from typing import cast

from aws_library.s3 import SimcoreS3API
from common_library.json_serialization import json_dumps
from servicelib.logging_utils import log_context
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_fixed

from ..constants import APP_CONFIG_KEY, APP_S3_KEY, RETRY_WAIT_SECS
from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


async def setup_s3_client(app) -> AsyncGenerator[None, None]:
    client = None

    with log_context(_logger, logging.DEBUG, msg="setup.s3_client.cleanup_ctx"):
        storage_settings: ApplicationSettings = app[APP_CONFIG_KEY]
        storage_s3_settings = storage_settings.STORAGE_S3
        assert storage_s3_settings  # nosec

        async for attempt in AsyncRetrying(
            wait=wait_fixed(RETRY_WAIT_SECS),
            before_sleep=before_sleep_log(_logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                client = await SimcoreS3API.create(
                    storage_s3_settings,
                    storage_settings.STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY,
                )
                _logger.info(
                    "S3 client %s successfully created [%s]",
                    f"{client=}",
                    json_dumps(attempt.retry_state.retry_object.statistics),
                )
            assert client  # nosec
            app[APP_S3_KEY] = client

    yield

    with log_context(_logger, logging.DEBUG, msg="teardown.s3_client.cleanup_ctx"):
        if client:
            await client.close()


async def setup_s3_bucket(app: FastAPI):
    with log_context(_logger, logging.DEBUG, msg="setup.s3_bucket.cleanup_ctx"):
        storage_s3_settings = app[APP_CONFIG_KEY].STORAGE_S3
        client = get_s3_client(app)
        await client.create_bucket(
            bucket=storage_s3_settings.S3_BUCKET_NAME,
            region=storage_s3_settings.S3_REGION,
        )
    yield


def setup_s3(app: FastAPI):
    if setup_s3_client not in app.cleanup_ctx:
        app.cleanup_ctx.append(setup_s3_client)
    if setup_s3_bucket not in app.cleanup_ctx:
        app.cleanup_ctx.append(setup_s3_bucket)


def get_s3_client(app: FastAPI) -> SimcoreS3API:
    assert app[APP_S3_KEY]  # nosec
    assert isinstance(app[APP_S3_KEY], SimcoreS3API)  # nosec
    return cast(SimcoreS3API, app[APP_S3_KEY])
