import logging
from collections.abc import AsyncIterator
from typing import cast

from aws_library.s3 import S3NotConnectedError, SimcoreS3API
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.api_schemas_storage.storage_schemas import S3BucketName
from pydantic import TypeAdapter
from servicelib.logging_utils import log_context
from settings_library.s3 import S3Settings
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    stop_after_delay,
    wait_random_exponential,
)

from ...exceptions.errors import ConfigurationError

_logger = logging.getLogger(__name__)


def configure_s3(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _s3_lifespan(app: FastAPI) -> AsyncIterator[State]:
        app.state.s3_client = None
        try:
            with log_context(_logger, logging.INFO, msg="RUT startup S3"):
                settings: S3Settings | None = app.state.settings.RESOURCE_USAGE_TRACKER_S3

                if not settings:
                    _logger.warning("S3 client is de-activated in the settings")
                    yield {}
                    return

                app.state.s3_client = client = await SimcoreS3API.create(settings)

                async for attempt in AsyncRetrying(
                    reraise=True,
                    stop=stop_after_delay(120),
                    wait=wait_random_exponential(max=30),
                    before_sleep=before_sleep_log(_logger, logging.WARNING),
                ):
                    with attempt:
                        connected = await client.http_check_bucket_connected(
                            bucket=TypeAdapter(S3BucketName).validate_python(settings.S3_BUCKET_NAME)
                        )
                        if not connected:
                            raise S3NotConnectedError  # pragma: no cover
            yield {}
        finally:
            if app.state.s3_client:
                with log_context(_logger, logging.INFO, msg="RUT shutdown S3"):
                    await cast(SimcoreS3API, app.state.s3_client).close()

    app_lifespan.add(_s3_lifespan)


def get_s3_client(app: FastAPI) -> SimcoreS3API:
    if not app.state.s3_client:
        raise ConfigurationError(msg="S3 client is not available. Please check the configuration.")
    return cast(SimcoreS3API, app.state.s3_client)
