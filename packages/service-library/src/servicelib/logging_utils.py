"""
This codes originates from this article
    https://medium.com/swlh/add-log-decorators-to-your-python-project-84094f832181

SEE also https://github.com/Delgan/loguru for a future alternative
"""

import asyncio
import functools
import logging
import logging.handlers
import queue
from asyncio import iscoroutinefunction
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from inspect import getframeinfo, stack
from pathlib import Path
from typing import Any, Final, TypeAlias, TypedDict, TypeVar

from common_library.json_serialization import json_dumps
from common_library.logging.logging_base import LogExtra
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from common_library.logging.logging_utils_filtering import (
    GeneralLogFilter,
    LoggerName,
    MessageSubstring,
)

from .tracing import TracingConfig, setup_log_tracing
from .utils_secrets import mask_sensitive_data

_logger = logging.getLogger(__name__)

LogLevelInt: TypeAlias = int
LogMessageStr: TypeAlias = str

BLACK = "\033[0;30m"
BLUE = "\033[0;34m"
GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
RED = "\033[0;31m"
ORANGE = "\033[48;2;255;165;0m"
PURPLE = "\033[0;35m"
BROWN = "\033[0;33m"
GRAY = "\033[0;37m"
BOLDGRAY = "\033[1;30m"
BOLDBLUE = "\033[1;34m"
BOLDGREEN = "\033[1;32m"
BOLDCYAN = "\033[1;36m"
BOLDRED = "\033[1;31m"
BOLDPURPLE = "\033[1;35m"
BOLDYELLOW = "\033[1;33m"
WHITE = "\033[1;37m"

NORMAL = "\033[0m"

COLORS = {
    "WARNING": BOLDYELLOW,
    "INFO": GREEN,
    "DEBUG": GRAY,
    "CRITICAL": ORANGE,
    "ERROR": RED,
}


class CustomFormatter(logging.Formatter):
    """Custom Formatter does these 2 things:
    1. Overrides 'funcName' with the value of 'func_name_override', if it exists.
    2. Overrides 'filename' with the value of 'file_name_override', if it exists.
    """

    def __init__(self, fmt: str, *, log_format_local_dev_enabled: bool) -> None:
        super().__init__(fmt)
        self.log_format_local_dev_enabled = log_format_local_dev_enabled

    def format(self, record) -> str:
        if hasattr(record, "func_name_override"):
            record.funcName = (
                record.func_name_override
            )  # pyright: ignore[reportAttributeAccessIssue]
        if hasattr(record, "file_name_override"):
            record.filename = (
                record.file_name_override
            )  # pyright: ignore[reportAttributeAccessIssue]

        # pylint: disable=no-member
        optional_keys = LogExtra.__optional_keys__ | frozenset(
            ["otelTraceID", "otelSpanID"]
        )
        for name in optional_keys:
            if not hasattr(record, name):
                setattr(record, name, None)

        if self.log_format_local_dev_enabled:
            levelname = record.levelname
            if levelname in COLORS:
                levelname_color = COLORS[levelname] + levelname + NORMAL
                record.levelname = levelname_color
            return super().format(record)

        return super().format(record).replace("\n", "\\n")


# SEE https://docs.python.org/3/library/logging.html#logrecord-attributes
_DEFAULT_FORMATTING: Final[str] = " | ".join(
    [
        "log_level=%(levelname)s",
        "log_timestamp=%(asctime)s",
        "log_source=%(name)s:%(funcName)s(%(lineno)d)",
        "log_uid=%(log_uid)s",
        "log_oec=%(log_oec)s",
        "log_trace_id=%(otelTraceID)s",
        "log_span_id=%(otelSpanID)s",
        "log_msg=%(message)s",
    ]
)

_LOCAL_FORMATTING: Final[str] = (
    "%(levelname)s: [%(asctime)s/%(processName)s] "
    "[log_trace_id=%(otelTraceID)s|log_span_id=%(otelSpanID)s] "
    "[%(name)s:%(funcName)s(%(lineno)d)] -  %(message)s"
)

# Graylog Grok pattern extractor:
# log_level=%{WORD:log_level} \| log_timestamp=%{TIMESTAMP_ISO8601:log_timestamp} \| log_source=%{NOTSPACE:log_source} \| log_uid=%{NOTSPACE:log_uid} \| log_oec=%{NOTSPACE:log_oec} \| log_trace_id=%{NOTSPACE:log_trace_id} \| log_span_id=%{NOTSPACE:log_span_id} \| log_msg=%{GREEDYDATA:log_msg}


def _setup_logging_formatter(
    *,
    log_format_local_dev_enabled: bool,
) -> logging.Formatter:
    fmt = _LOCAL_FORMATTING if log_format_local_dev_enabled else _DEFAULT_FORMATTING

    return CustomFormatter(
        fmt, log_format_local_dev_enabled=log_format_local_dev_enabled
    )


def _get_all_loggers() -> list[logging.Logger]:
    manager = logging.Logger.manager
    root_logger = logging.getLogger()
    return [root_logger] + [logging.getLogger(name) for name in manager.loggerDict]


def _apply_logger_filters(
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
) -> None:
    for logger_name, filtered_routes in logger_filter_mapping.items():
        logger = logging.getLogger(logger_name)
        if not logger.hasHandlers():
            _logger.warning(
                "Logger %s does not have any handlers. Filter will not be added.",
                logger_name,
            )
            continue

        log_filter = GeneralLogFilter(filtered_routes)
        logger.addFilter(log_filter)


def _setup_base_logging_level(log_level: LogLevelInt) -> None:
    logging.basicConfig(level=log_level)
    logging.root.setLevel(log_level)


def _dampen_noisy_loggers(
    noisy_loggers: tuple[str, ...],
) -> None:
    """Sets a less verbose level for noisy loggers."""
    quiet_level: int = max(
        min(logging.root.level + logging.CRITICAL - logging.ERROR, logging.CRITICAL),
        logging.WARNING,
    )

    for name in noisy_loggers:
        logging.getLogger(name).setLevel(quiet_level)


def _configure_common_logging_settings(
    *,
    log_format_local_dev_enabled: bool,
    tracing_config: TracingConfig,
    log_base_level: LogLevelInt,
    noisy_loggers: tuple[str, ...] | None,
) -> logging.Formatter:
    """
    Common configuration logic shared by both sync and async logging setups.

    Returns the configured formatter to be used with the appropriate handler.
    """
    _setup_base_logging_level(log_base_level)
    if noisy_loggers is not None:
        _dampen_noisy_loggers(noisy_loggers)
    setup_log_tracing(tracing_config=tracing_config)
    return _setup_logging_formatter(
        log_format_local_dev_enabled=log_format_local_dev_enabled,
    )


def _apply_logging_configuration(
    handler: logging.Handler,
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
) -> None:
    """
    Apply the logging configuration with the given handler.
    """
    _clean_all_handlers()
    _set_root_handler(handler)

    if logger_filter_mapping:
        _apply_logger_filters(logger_filter_mapping)


def setup_loggers(
    *,
    log_format_local_dev_enabled: bool,
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
    tracing_config: TracingConfig,
    log_base_level: LogLevelInt,
    noisy_loggers: tuple[str, ...] | None,
) -> None:
    """
    Applies comprehensive configuration to ALL registered loggers.

    Flow Diagram (Synchronous Logging):
    ┌─────────────────┐                    ┌─────────────────┐
    │ Application     │                    │ Root Logger     │
    │ Thread          │───────────────────▶│ StreamHandler   │
    │                 │                    │ ├─ Formatter    │
    │ logger.info()   │                    │ └─ Output       │
    │ logger.error()  │                    │                 │
    │ (blocking I/O)  │                    │                 │
    └─────────────────┘                    └─────────────────┘
           │                                       │
           │                                       ▼
           │                                ┌─────────────┐
           │                                │ Console/    │
           │                                │ Terminal    │
           │                                └─────────────┘
           │
           └─ Blocks until I/O completes

    This function uses a comprehensive approach:
    - Removes all handlers from all loggers
    - Ensures all loggers propagate to root
    - Sets up root logger with properly formatted handler
    - All logging calls are synchronous and may block on I/O

    For async/non-blocking logging, use `async_loggers` context manager instead.

    Args:
        log_format_local_dev_enabled: Enable local development formatting
        logger_filter_mapping: Mapping of logger names to filtered message substrings
        tracing_settings: OpenTelemetry tracing configuration
        log_base_level: Base logging level to set
        noisy_loggers: Loggers to set to a quieter level
    """
    formatter = _configure_common_logging_settings(
        log_format_local_dev_enabled=log_format_local_dev_enabled,
        tracing_config=tracing_config,
        log_base_level=log_base_level,
        noisy_loggers=noisy_loggers,
    )

    # Create a properly formatted handler for the root logger
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    _store_logger_state(_get_all_loggers())
    _apply_logging_configuration(stream_handler, logger_filter_mapping)


@contextmanager
def _queued_logging_handler(
    log_formatter: logging.Formatter,
) -> Iterator[logging.Handler]:
    log_queue: queue.Queue[logging.LogRecord] = queue.Queue()
    # Create handler with proper formatting
    handler = logging.StreamHandler()
    handler.setFormatter(log_formatter)

    # Create and start the queue listener
    listener = logging.handlers.QueueListener(
        log_queue, handler, respect_handler_level=True
    )
    listener.start()

    queue_handler = logging.handlers.QueueHandler(log_queue)

    yield queue_handler

    # cleanup
    with log_context(
        _logger,
        level=logging.DEBUG,
        msg="Shutdown async logging listener",
    ):
        listener.stop()


def _clean_all_handlers() -> None:
    """
    Cleans all handlers from all loggers.
    This is useful for resetting the logging configuration.
    """
    root_logger = logging.getLogger()
    all_loggers = _get_all_loggers()
    for logger in all_loggers:
        if logger is root_logger:
            continue
        logger.handlers.clear()
        logger.propagate = True  # Ensure propagation is enabled


def _set_root_handler(handler: logging.Handler) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Clear existing handlers
    root_logger.addHandler(handler)  # Add the new handler


@contextmanager
def async_loggers(
    *,
    log_format_local_dev_enabled: bool,
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
    tracing_config: TracingConfig,
    log_base_level: LogLevelInt,
    noisy_loggers: tuple[str, ...] | None,
) -> Iterator[None]:
    """
    Context manager for non-blocking logging infrastructure.

    Flow Diagram:
    ┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
    │ Application     │    │ Queue        │    │ Background      │
    │ Thread          │───▶│ (unlimited)  │───▶│ Listener Thread │
    │                 │    │              │    │                 │
    │ logger.info()   │    │ LogRecord    │    │ StreamHandler   │
    │ logger.error()  │    │ LogRecord    │    │ ├─ Formatter    │
    │ (non-blocking)  │    │ LogRecord    │    │ └─ Output       │
    └─────────────────┘    └──────────────┘    └─────────────────┘
           │                       │                       │
           │                       │                       ▼
           │                       │                ┌─────────────┐
           │                       │                │ Console/    │
           │                       │                │ Terminal    │
           │                       │                └─────────────┘
           │                       │
           └───────────────────────┴─ No blocking, immediate return

    The async logging setup ensures that:
    1. All log calls return immediately (non-blocking)
    2. Log records are queued in an unlimited queue
    3. A background thread processes the queue and handles actual I/O
    4. All loggers propagate to root for centralized handling

    For more details on the underlying implementation, see:
    https://docs.python.org/3/library/logging.handlers.html#queuehandler

    Usage:
        with async_loggers(log_format_local_dev_enabled=True, logger_filter_mapping={}, tracing_settings=None):
            # Your async application code here
            logger.info("This is non-blocking!")

    Args:
        log_format_local_dev_enabled: Enable local development formatting
        logger_filter_mapping: Mapping of logger names to filtered message substrings
        tracing_settings: OpenTelemetry tracing configuration
        log_base_level: Base logging level to set
        noisy_loggers: Loggers to set to a quieter level
    """
    formatter = _configure_common_logging_settings(
        log_format_local_dev_enabled=log_format_local_dev_enabled,
        tracing_config=tracing_config,
        log_base_level=log_base_level,
        noisy_loggers=noisy_loggers,
    )

    with (
        _queued_logging_handler(formatter) as queue_handler,
        _stored_logger_states(_get_all_loggers()),
    ):
        _apply_logging_configuration(queue_handler, logger_filter_mapping)

        with log_context(_logger, logging.INFO, "Asynchronous logging"):
            yield


class LogExceptionsKwargsDict(TypedDict, total=True):
    logger: logging.Logger
    level: LogLevelInt
    msg_prefix: str
    exc_info: bool
    stack_info: bool


@contextmanager
def log_exceptions(
    logger: logging.Logger,
    level: LogLevelInt,
    msg_prefix: str = "",
    *,
    exc_info: bool = False,
    stack_info: bool = False,
) -> Iterator[None]:
    """If an exception is raised, it gets logged with level.

    NOTE that this does NOT suppress exceptions

    Example: logging exceptions raised a "section of code" for debugging purposes

    # raises
    with log_exceptions(logger, logging.DEBUG):
        # ...
        resp.raise_for_status()

    # does NOT raises  (NOTE: use composition of context managers)
    with suppress(Exception), log_exceptions(logger, logging.DEBUG):
        # ...
        resp.raise_for_status()
    """
    try:
        yield
    except asyncio.CancelledError:
        msg = f"{msg_prefix} call cancelled ".strip()
        logger.log(level, msg)
        raise
    except Exception as exc:  # pylint: disable=broad-except
        msg = f"{msg_prefix} raised {type(exc).__name__}: {exc}".strip()
        logger.log(
            level,
            msg,
            exc_info=exc_info,
            stack_info=stack_info,
        )
        raise


def _log_before_call(
    logger_obj: logging.Logger, level: LogLevelInt, func: Callable, *args, **kwargs
) -> dict[str, str]:
    # NOTE: We should avoid logging arguments but in the meantime, we are trying to
    # avoid exposing sensitive data in the logs. For `args` is more difficult. We could eventually
    # deduced sensitivity based on the entropy of values but it is very costly
    # SEE https://github.com/ITISFoundation/osparc-simcore/security/code-scanning/18
    args_passed_in_function = [repr(a) for a in args]
    masked_kwargs = mask_sensitive_data(kwargs)
    kwargs_passed_in_function = [f"{k}={v!r}" for k, v in masked_kwargs.items()]

    # The lists of positional and keyword arguments is joined together to form final string
    formatted_arguments = ", ".join(args_passed_in_function + kwargs_passed_in_function)

    # Generate file name and function name for calling function. __func.name__ will give the name of the
    #     caller function ie. wrapper_log_info and caller file name ie log-decorator.py
    # - In order to get actual function and file name we will use 'extra' parameter.
    # - To get the file name we are using in-built module inspect.getframeinfo which returns calling file name
    py_file_caller = getframeinfo(stack()[1][0])
    extra_args = {
        "func_name_override": func.__name__,
        "file_name_override": Path(py_file_caller.filename).name,
    }

    #  Before to the function execution, log function details.
    logger_obj.log(
        level,
        "%s:%s(%s) - Begin function",
        func.__module__.split(".")[-1],
        func.__name__,
        formatted_arguments,
        extra=extra_args,
    )

    return extra_args


def _log_after_call(
    logger_obj: logging.Logger,
    level: LogLevelInt,
    func: Callable,
    result: Any,
    extra_args: dict[str, str],
) -> None:
    logger_obj.log(
        level,
        "%s:%s returned %r - End function",
        func.__module__.split(".")[-1],
        func.__name__,
        result,
        extra=extra_args,
    )


F = TypeVar("F", bound=Callable[..., Any])


def log_decorator(
    logger: logging.Logger | None,
    level: LogLevelInt = logging.DEBUG,
    *,
    # NOTE: default defined by legacy: ANE defined full stack tracebacks
    # on exceptions
    exc_info: bool = True,
    exc_stack_info: bool = True,
) -> Callable[[F], F]:
    """Logs the decorated function:
    - *before* its called
        - input parameters
    - *after* its called
        - returned values *after* the decorated function is executed *or*
        - raised exception (w/ or w/o traceback)
    """
    logger_obj = logger or _logger

    def _decorator(func_or_coro: F) -> F:
        _log_exc_kwargs = LogExceptionsKwargsDict(
            logger=logger_obj,
            level=level,
            msg_prefix=f"{func_or_coro.__name__}",
            exc_info=exc_info,
            stack_info=exc_stack_info,
        )

        if iscoroutinefunction(func_or_coro):

            @functools.wraps(func_or_coro)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                extra_args = _log_before_call(
                    logger_obj, level, func_or_coro, *args, **kwargs
                )
                with log_exceptions(**_log_exc_kwargs):
                    result = await func_or_coro(*args, **kwargs)
                _log_after_call(logger_obj, level, func_or_coro, result, extra_args)
                return result

            return _async_wrapper  # type: ignore[return-value] # decorators typing is hard

        @functools.wraps(func_or_coro)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            extra_args = _log_before_call(
                logger_obj, level, func_or_coro, *args, **kwargs
            )
            with log_exceptions(**_log_exc_kwargs):
                result = func_or_coro(*args, **kwargs)
            _log_after_call(logger_obj, level, func_or_coro, result, extra_args)
            return result

        return _sync_wrapper  # type: ignore[return-value] # decorators typing is hard

    return _decorator


@contextmanager
def log_catch(logger: logging.Logger, *, reraise: bool = True) -> Iterator[None]:
    try:
        yield
    except asyncio.CancelledError:
        logger.debug("call was cancelled")
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            **create_troubleshooting_log_kwargs(
                "Caught unhandled exception",
                error=exc,
            )
        )
        if reraise:
            raise exc from exc


def _un_capitalize(s: str) -> str:
    return s[:1].lower() + s[1:] if s else ""


@contextmanager
def log_context(
    logger: logging.Logger,
    level: LogLevelInt,
    msg: LogMessageStr,
    *args,
    log_duration: bool = False,
    extra: LogExtra | None = None,
):
    # NOTE: preserves original signature https://docs.python.org/3/library/logging.html#logging.Logger.log
    start = datetime.now()  # noqa: DTZ005
    msg = _un_capitalize(msg.strip())

    kwargs: dict[str, Any] = {}
    if extra:
        kwargs["extra"] = extra
    log_msg = f"Starting {msg} ..."

    stackelvel = 3  # NOTE: 1 => log_context, 2 => contextlib, 3 => caller
    logger.log(level, log_msg, *args, **kwargs, stacklevel=stackelvel)
    yield
    duration = (
        f" in {(datetime.now() - start).total_seconds()}s"  # noqa: DTZ005
        if log_duration
        else ""
    )
    log_msg = f"Finished {msg}{duration}"
    logger.log(level, log_msg, *args, **kwargs, stacklevel=stackelvel)


def guess_message_log_level(message: str) -> LogLevelInt:
    lower_case_message = message.lower().strip()
    if lower_case_message.startswith(
        (
            "error",
            "[error]",
            "err",
            "[err]",
            "exception",
            "[exception]",
            "exc:",
            "exc ",
            "[exc]",
        )
    ):
        return logging.ERROR
    if lower_case_message.startswith(
        (
            "warning",
            "[warning]",
            "warn",
            "[warn]",
        )
    ):
        return logging.WARNING
    return logging.INFO


def set_parent_module_log_level(
    current_module: str, desired_log_level: LogLevelInt
) -> None:
    parent_module = ".".join(current_module.split(".")[:-1])
    logging.getLogger(parent_module).setLevel(desired_log_level)


@dataclass(frozen=True)
class _LoggerState:
    logger: logging.Logger
    handlers: list[logging.Handler]
    propagate: bool


@contextmanager
def _stored_logger_states(
    loggers: list[logging.Logger],
) -> Iterator[list[_LoggerState]]:
    """
    Context manager to store and restore the state of loggers.
    It captures the current handlers and propagation state of each logger.
    """
    original_state = _store_logger_state(loggers)

    try:
        yield original_state
    finally:
        _restore_logger_state(original_state)


def _store_logger_state(loggers: list[logging.Logger]) -> list[_LoggerState]:
    logger_states = [
        _LoggerState(logger, logger.handlers.copy(), logger.propagate)
        for logger in loggers
        if logger.handlers or not logger.propagate
    ]
    # log which loggers states were stored
    _logger.info(
        "Stored logger states: %s. TIP: these loggers configuration will be restored later.",
        json_dumps(
            [
                f"{state.logger.name}(handlers={len(state.handlers)}, propagate={state.propagate})"
                for state in logger_states
            ]
        ),
    )
    return logger_states


def _restore_logger_state(original_state: list[_LoggerState]) -> None:
    for state in original_state:
        logger = state.logger
        logger.handlers.clear()
        logger.handlers.extend(state.handlers)
        logger.propagate = state.propagate
