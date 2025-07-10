"""Main application to be deployed in for example uvicorn."""

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Final

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from servicelib.logging_utils import setup_async_loggers_lifespan
from simcore_service_catalog.core.application import create_app
from simcore_service_catalog.core.events import Lifespan
from simcore_service_catalog.core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "aio_pika",
    "aiobotocore",
    "aiormq",
    "botocore",
    "httpcore",
    "werkzeug",
)


async def _setup_logging(app_settings: ApplicationSettings) -> Lifespan:
    exit_stack = AsyncExitStack()
    await exit_stack.enter_async_context(
        setup_async_loggers_lifespan(
            log_base_level=app_settings.log_level,
            noisy_loggers=_NOISY_LOGGERS,
            log_format_local_dev_enabled=app_settings.CATALOG_LOG_FORMAT_LOCAL_DEV_ENABLED,
            logger_filter_mapping=app_settings.CATALOG_LOG_FILTER_MAPPING,
            tracing_settings=app_settings.CATALOG_TRACING,
        )
    )

    async def _logging_lifespan(app: FastAPI) -> AsyncIterator[None]:
        assert app is not None, "app must be provided"
        _logger.info("This is the non-blocking logger! Congratulations!")
        yield
        await exit_stack.aclose()
        _logger.info("This is the blocking logger! Back to the roots!")

    return _logging_lifespan


async def app_factory() -> FastAPI:
    app_settings = ApplicationSettings.create_from_envs()
    _logger.info(
        "Application settings: %s",
        json_dumps(app_settings, indent=2, sort_keys=True),
    )

    logging_lifespan = await _setup_logging(app_settings)

    return create_app(logging_lifespan=logging_lifespan)
