""" Configuration and utilities for service logging

"""
import logging
import os
from typing import Union

from aiodebug import log_slow_callbacks
from aiohttp.log import access_logger

from servicelib.logging_utils import set_logging_handler

LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR


def setup_logging(*, level: Union[str, int]):
    # service log level
    logging.basicConfig(level=level)
    logging.root.setLevel(level)
    set_logging_handler(logging.root)

    # aiohttp access log-levels
    access_logger.setLevel(level)

    # keep mostly quiet noisy loggers
    quiet_level = max(min(level + LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING)
    logging.getLogger("engineio").setLevel(quiet_level)
    logging.getLogger("openapi_spec_validator").setLevel(quiet_level)
    logging.getLogger("sqlalchemy").setLevel(quiet_level)
    logging.getLogger("sqlalchemy.engine").setLevel(quiet_level)

    # NOTE: Every task blocking > AIODEBUG_SLOW_DURATION_SECS secs is considered slow and logged as warning
    slow_duration = float(os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 0.1))
    log_slow_callbacks.enable(slow_duration)


def test_logger_propagation(logger: logging.Logger):
    msg = f"TESTING %s log with {logger}"
    logger.critical(msg, "critical")
    logger.error(msg, "error")
    logger.info(msg, "info")
    logger.warning(msg, "warning")
    logger.debug(msg, "debug")
