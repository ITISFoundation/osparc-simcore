"""
This codes originates from this article
    https://medium.com/swlh/add-log-decorators-to-your-python-project-84094f832181

SEE also https://github.com/Delgan/loguru for a future alternative
"""

import asyncio
import functools
import logging
from asyncio import iscoroutinefunction
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from inspect import getframeinfo, stack
from pathlib import Path
from typing import Any, TypeAlias, TypedDict, TypeVar

from .utils_secrets import mask_sensitive_data

_logger = logging.getLogger(__name__)


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
            record.funcName = record.func_name_override
        if hasattr(record, "file_name_override"):
            record.filename = record.file_name_override
        if not hasattr(record, "log_uid"):
            record.log_uid = None  # Default value if user is not provided in the log

        if self.log_format_local_dev_enabled:
            levelname = record.levelname
            if levelname in COLORS:
                levelname_color = COLORS[levelname] + levelname + NORMAL
                record.levelname = levelname_color
            return super().format(record)

        return super().format(record).replace("\n", "\\n")


# SEE https://docs.python.org/3/library/logging.html#logrecord-attributes
DEFAULT_FORMATTING = "log_level=%(levelname)s | log_timestamp=%(asctime)s | log_source=%(name)s:%(funcName)s(%(lineno)d) | log_uid=%(log_uid)s | log_msg=%(message)s"
LOCAL_FORMATTING = "%(levelname)s: [%(asctime)s/%(processName)s] [%(name)s:%(funcName)s(%(lineno)d)]  -  %(message)s"

# Graylog Grok pattern extractor:
# log_level=%{WORD:log_level} \| log_timestamp=%{TIMESTAMP_ISO8601:log_timestamp} \| log_source=%{DATA:log_source} \| log_msg=%{GREEDYDATA:log_msg}


def config_all_loggers(*, log_format_local_dev_enabled: bool) -> None:
    """
    Applies common configuration to ALL registered loggers
    """
    fmt = DEFAULT_FORMATTING
    the_manager: logging.Manager = logging.Logger.manager
    root_logger = logging.getLogger()

    loggers = [root_logger] + [
        logging.getLogger(name) for name in the_manager.loggerDict
    ]

    if log_format_local_dev_enabled:
        fmt = LOCAL_FORMATTING

    for logger in loggers:
        set_logging_handler(
            logger, fmt=fmt, log_format_local_dev_enabled=log_format_local_dev_enabled
        )


def set_logging_handler(
    logger: logging.Logger,
    *,
    fmt: str,
    log_format_local_dev_enabled: bool,
) -> None:
    for handler in logger.handlers:
        handler.setFormatter(
            CustomFormatter(
                fmt, log_format_local_dev_enabled=log_format_local_dev_enabled
            )
        )


def test_logger_propagation(logger: logging.Logger) -> None:
    """log propagation and levels can sometimes be daunting to get it right.

    This function uses the `logger`` passed as argument to log the same message at different levels

    This should help to visually test a given configuration

    USAGE:
        from .logging_utils import test_logger_propagation
        for n in ("aiohttp.access", "gunicorn.access"):
            test_logger_propagation(logging.getLogger(n))
    """
    msg = f"TESTING %s log using {logger=}"
    logger.critical(msg, "critical")
    logger.error(msg, "error")
    logger.info(msg, "info")
    logger.warning(msg, "warning")
    logger.debug(msg, "debug")


class LogExceptionsKwargsDict(TypedDict, total=True):
    logger: logging.Logger
    level: int
    msg_prefix: str
    exc_info: bool
    stack_info: bool


@contextmanager
def log_exceptions(
    logger: logging.Logger,
    level: int,
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
    logger_obj: logging.Logger, level: int, func: Callable, *args, **kwargs
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
    level: int,
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
    level: int = logging.DEBUG,
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
        logger.exception("Unhandled exception:")
        if reraise:
            raise exc from exc


class LogExtra(TypedDict, total=False):
    log_uid: str


LogLevelInt: TypeAlias = int
LogMessageStr: TypeAlias = str


def get_log_record_extra(*, user_id: int | str | None = None) -> LogExtra | None:
    extra: LogExtra = {}
    if user_id:
        assert int(user_id) > 0  # nosec
        extra["log_uid"] = f"{user_id}"
    return extra or None


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
    logger.log(level, log_msg, *args, **kwargs)
    yield
    duration = (
        f" in {(datetime.now() - start ).total_seconds()}s"  # noqa: DTZ005
        if log_duration
        else ""
    )
    log_msg = f"Finished {msg}{duration}"
    logger.log(level, log_msg, *args, **kwargs)


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
