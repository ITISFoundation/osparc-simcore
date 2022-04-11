""" Configuration and utilities for service logging

"""
import logging
from typing import Optional, Union

from aiodebug import log_slow_callbacks
from aiohttp.log import access_logger
from servicelib.logging_utils import config_all_loggers

LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR
NOISY_LOGGERS = (
    "engineio",
    "openapi_spec_validator",
    "sqlalchemy",
    "sqlalchemy.engine",
    "inotify.adapters",
    "servicelib.aiohttp.monitoring",
)


def setup_logging(*, level: Union[str, int], slow_duration: Optional[float] = None):
    # service log level
    logging.basicConfig(level=level)

    # root
    logging.root.setLevel(level)
    config_all_loggers()

    # aiohttp access log-levels
    access_logger.setLevel(level)

    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(quiet_level)

    if slow_duration:
        # NOTE: Every task blocking > AIODEBUG_SLOW_DURATION_SECS secs is considered slow and logged as warning
        log_slow_callbacks.enable(abs(slow_duration))


def test_logger_propagation(logger: logging.Logger):
    msg = f"TESTING %s log with {logger}"
    logger.critical(msg, "critical")
    logger.error(msg, "error")
    logger.info(msg, "info")
    logger.warning(msg, "warning")
    logger.debug(msg, "debug")
