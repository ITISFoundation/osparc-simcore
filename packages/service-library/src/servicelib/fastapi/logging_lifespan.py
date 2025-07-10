import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack

from fastapi import FastAPI
from settings_library.tracing import TracingSettings

from ..logging_utils import (
    LogLevelInt,
    log_context,
    setup_async_loggers_lifespan,
)
from ..logging_utils_filtering import LoggerName, MessageSubstring
from .lifespan_utils import Lifespan

_logger = logging.getLogger(__name__)


def setup_logging_lifespan(
    *,
    log_format_local_dev_enabled: bool,
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
    tracing_settings: TracingSettings | None,
    log_base_level: LogLevelInt,
    noisy_loggers: tuple[str, ...] | None,
) -> Lifespan:
    exit_stack = AsyncExitStack()
    exit_stack.enter_context(
        setup_async_loggers_lifespan(
            log_base_level=log_base_level,
            noisy_loggers=noisy_loggers,
            log_format_local_dev_enabled=log_format_local_dev_enabled,
            logger_filter_mapping=logger_filter_mapping,
            tracing_settings=tracing_settings,
        )
    )

    async def _logging_lifespan(app: FastAPI) -> AsyncIterator[None]:
        assert app is not None, "app must be provided"
        with log_context(_logger, logging.INFO, "Non-blocking logger!"):
            yield
            await exit_stack.aclose()

    return _logging_lifespan
