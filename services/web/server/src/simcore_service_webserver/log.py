"""Configuration and utilities for service logging"""

import logging

from aiodebug import log_slow_callbacks  # type: ignore[import-untyped]
from aiohttp.log import access_logger
from settings_library.tracing import TracingSettings

LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
NOISY_LOGGERS = (
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


def setup_logging(
    *,
    level: str | int,
    slow_duration: float | None = None,
    log_format_local_dev_enabled: bool,
    logger_filter_mapping: dict,
    tracing_settings: TracingSettings | None,
):
    # service log level
    logging.basicConfig(level=level)

    # root
    logging.root.setLevel(level)

    # Enforces same log-level to aiohttp & gunicorn access loggers
    #
    # NOTE: gunicorn access_log is hard-coded to INFO (SEE https://github.com/benoitc/gunicorn/blob/master/gunicorn/glogging.py#L200)
    # and the option passed through command line is for access_log.
    # Our changes in root do not affect this config because
    # they are not applied globally but only upon setup_logging ...
    #
    gunicorn_access_log = logging.getLogger("gunicorn.access")
    access_logger.setLevel(level)
    gunicorn_access_log.setLevel(level)

    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

    if slow_duration:
        # NOTE: Every task blocking > AIODEBUG_SLOW_DURATION_SECS secs is considered slow and logged as warning
        log_slow_callbacks.enable(abs(slow_duration))
