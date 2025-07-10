"""Configuration and utilities for service logging"""

import logging
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Final, TypeAlias

from aiodebug import log_slow_callbacks  # type: ignore[import-untyped]
from aiohttp import web
from aiohttp.log import access_logger
from servicelib.logging_utils import setup_async_loggers_lifespan
from simcore_service_webserver.application_settings import ApplicationSettings

_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "aio_pika",
    "aiormq",
    "engineio",
    "engineio.server",
    "inotify.adapters",
    "openapi_spec_validator",
    "servicelib.aiohttp.monitoring",
    "socketio",
    "socketio.server",
    "sqlalchemy.engine",
    "sqlalchemy",
)

_logger = logging.getLogger(__name__)

CleanupEvent: TypeAlias = Callable[[web.Application], Awaitable[None]]


def setup_logging(app_settings: ApplicationSettings) -> CleanupEvent:
    exit_stack = AsyncExitStack()
    exit_stack.enter_context(
        setup_async_loggers_lifespan(
            log_base_level=app_settings.log_level,
            noisy_loggers=_NOISY_LOGGERS,
            log_format_local_dev_enabled=app_settings.WEBSERVER_LOG_FORMAT_LOCAL_DEV_ENABLED,
            logger_filter_mapping=app_settings.WEBSERVER_LOG_FILTER_MAPPING,
            tracing_settings=app_settings.WEBSERVER_TRACING,
        )
    )

    # Enforces same log-level to aiohttp & gunicorn access loggers
    #
    # NOTE: gunicorn access_log is hard-coded to INFO (SEE https://github.com/benoitc/gunicorn/blob/master/gunicorn/glogging.py#L200)
    # and the option passed through command line is for access_log.
    # Our changes in root do not affect this config because
    # they are not applied globally but only upon setup_logging ...
    #
    gunicorn_access_log = logging.getLogger("gunicorn.access")
    access_logger.setLevel(app_settings.log_level)
    gunicorn_access_log.setLevel(app_settings.log_level)

    if app_settings.AIODEBUG_SLOW_DURATION_SECS:
        # NOTE: Every task blocking > AIODEBUG_SLOW_DURATION_SECS secs is considered slow and logged as warning
        log_slow_callbacks.enable(abs(app_settings.AIODEBUG_SLOW_DURATION_SECS))

    async def _cleanup_event(app: web.Application) -> None:
        assert app  # nosec
        _logger.info("Cleaning up application resources")
        await exit_stack.aclose()

    return _cleanup_event
