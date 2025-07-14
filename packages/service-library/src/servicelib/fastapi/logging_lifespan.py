import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack

from fastapi import FastAPI
from settings_library.tracing import TracingSettings

from ..logging_utils import (
    LogLevelInt,
    async_loggers,
    log_context,
)
from ..logging_utils_filtering import LoggerName, MessageSubstring
from .lifespan_utils import Lifespan

_logger = logging.getLogger(__name__)


def logging_lifespan(
    *,
    log_format_local_dev_enabled: bool,
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
    tracing_settings: TracingSettings | None,
    log_base_level: LogLevelInt,
    noisy_loggers: tuple[str, ...] | None,
) -> Lifespan:
    """Returns a FastAPI-compatible lifespan handler to set up async logging."""
    exit_stack = AsyncExitStack()
    exit_stack.enter_context(
        async_loggers(
            log_base_level=log_base_level,
            noisy_loggers=noisy_loggers,
            log_format_local_dev_enabled=log_format_local_dev_enabled,
            logger_filter_mapping=logger_filter_mapping,
            tracing_settings=tracing_settings,
        )
    )

    async def _logging_lifespan(app: FastAPI) -> AsyncIterator[None]:
        assert app is not None, "app must be provided"
        yield
        with log_context(_logger, logging.INFO, "Re-enable Blocking logger"):
            await exit_stack.aclose()

    return _logging_lifespan


def create_logging_shutdown_event(
    *,
    log_format_local_dev_enabled: bool,
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
    tracing_settings: TracingSettings | None,
    log_base_level: LogLevelInt,
    noisy_loggers: tuple[str, ...] | None,
) -> Callable[[], Awaitable[None]]:
    """retruns a fastapi-compatible shutdown event handler to be used with old style lifespan
    handlers. This is useful for applications that do not use the new async lifespan
    handlers introduced in fastapi 0.100.0.

    Note: This function is for backwards compatibility only and will be removed in the future.
    setup_logging_lifespan should be used instead for new style lifespan handlers.
    """
    exit_stack = AsyncExitStack()
    exit_stack.enter_context(
        async_loggers(
            log_base_level=log_base_level,
            noisy_loggers=noisy_loggers,
            log_format_local_dev_enabled=log_format_local_dev_enabled,
            logger_filter_mapping=logger_filter_mapping,
            tracing_settings=tracing_settings,
        )
    )

    async def _on_shutdown_event() -> None:
        with log_context(_logger, logging.INFO, "Re-enable Blocking logger"):
            await exit_stack.aclose()

    return _on_shutdown_event
