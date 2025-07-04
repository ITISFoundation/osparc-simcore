"""Module to access s3 service"""

import logging
from typing import Literal, cast

from aws_library.s3 import SimcoreS3API
from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from pydantic import TypeAdapter
from servicelib.logging_utils import log_context
from tenacity import wait_exponential
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_fixed
from types_aiobotocore_s3.literals import BucketLocationConstraintType

from ..constants import RETRY_WAIT_SECS
from ..core.settings import get_application_settings
from ..exceptions.errors import ConfigurationError

_logger = logging.getLogger(__name__)


def setup_s3(app: FastAPI) -> None:
    async def _on_startup() -> None:
        app.state.s3_client = None
        settings = get_application_settings(app)

        async for attempt in AsyncRetrying(
            wait=wait_fixed(RETRY_WAIT_SECS),
            before_sleep=before_sleep_log(_logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                assert settings.STORAGE_S3  # nosec
                client = await SimcoreS3API.create(
                    settings.STORAGE_S3,
                    settings.STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY,
                )
                _logger.info(
                    "S3 client %s successfully created [%s]",
                    f"{client=}",
                    json_dumps(attempt.retry_state.retry_object.statistics),
                )
                assert client  # nosec
        app.state.s3_client = client

        async for attempt in AsyncRetrying(
            wait=wait_exponential(min=1),  # 1, 2, 4, 8, ...
            before_sleep=before_sleep_log(_logger, logging.WARNING),
            reraise=True,
        ):
            assert settings.STORAGE_S3  # nosec
            with attempt, log_context(
                _logger, logging.DEBUG, msg="setup.s3_bucket.cleanup_ctx"
            ):
                if await client.bucket_exists(
                    bucket=settings.STORAGE_S3.S3_BUCKET_NAME
                ):
                    _logger.info(
                        "S3 bucket %s exists already, skipping creation",
                        settings.STORAGE_S3.S3_BUCKET_NAME,
                    )
                    break
                await client.create_bucket(
                    bucket=settings.STORAGE_S3.S3_BUCKET_NAME,
                    region=TypeAdapter(
                        BucketLocationConstraintType | Literal["us-east-1"]
                    ).validate_python(settings.STORAGE_S3.S3_REGION),
                )

    async def _on_shutdown() -> None:
        if app.state.s3_client:
            await cast(SimcoreS3API, app.state.s3_client).close()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


def get_s3_client(app: FastAPI) -> SimcoreS3API:
    if not app.state.s3_client:
        raise ConfigurationError(
            msg="S3 client is not available. Please check the configuration."
        )
    return cast(SimcoreS3API, app.state.s3_client)
