""" Module to access s3 service

"""
import json
import logging
from contextlib import AsyncExitStack

from aiohttp import web
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_fixed

from .constants import APP_CONFIG_KEY, APP_S3_KEY, RETRY_WAIT_SECS
from .s3_client import StorageS3Client
from .settings import Settings

log = logging.getLogger(__name__)


async def setup_s3_client(app):
    log.debug("setup %s.setup.cleanup_ctx", __name__)
    # setup
    storage_settings: Settings = app[APP_CONFIG_KEY]
    storage_s3_settings = storage_settings.STORAGE_S3
    assert storage_s3_settings  # nosec

    async with AsyncExitStack() as exit_stack:
        client = None
        async for attempt in AsyncRetrying(
            wait=wait_fixed(RETRY_WAIT_SECS),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                client = await StorageS3Client.create(
                    exit_stack,
                    storage_s3_settings,
                    storage_settings.STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY,
                )
                log.info(
                    "S3 client %s successfully created [%s]",
                    f"{client=}",
                    json.dumps(attempt.retry_state.retry_object.statistics),
                )
        assert client  # nosec
        app[APP_S3_KEY] = client

        yield
        # tear-down
        log.debug("closing %s", f"{client=}")
    log.info("closed s3 client %s", f"{client=}")


async def setup_s3_bucket(app: web.Application):
    storage_s3_settings = app[APP_CONFIG_KEY].STORAGE_S3
    client = get_s3_client(app)
    await client.create_bucket(storage_s3_settings.S3_BUCKET_NAME)
    yield


def setup_s3(app: web.Application):
    """minio/s3 service setup"""

    log.debug("Setting up %s ...", __name__)

    if setup_s3_client not in app.cleanup_ctx:
        app.cleanup_ctx.append(setup_s3_client)
    if setup_s3_bucket not in app.cleanup_ctx:
        app.cleanup_ctx.append(setup_s3_bucket)


def get_s3_client(app: web.Application) -> StorageS3Client:
    assert app[APP_S3_KEY]  # nosec
    assert isinstance(app[APP_S3_KEY], StorageS3Client)
    return app[APP_S3_KEY]
