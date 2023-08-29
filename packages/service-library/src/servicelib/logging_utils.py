"""
This codes originates from this article
    https://medium.com/swlh/add-log-decorators-to-your-python-project-84094f832181

SEE also https://github.com/Delgan/loguru for a future alternative
"""
import asyncio
import functools
import logging
import os
import sys
from asyncio import iscoroutinefunction
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from inspect import getframeinfo, stack
from typing import TypeAlias, TypedDict

log = logging.getLogger(__name__)


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

    def __init__(self, fmt: str, log_format_local_dev_enabled: bool):
        super().__init__(fmt)
        self.log_format_local_dev_enabled = log_format_local_dev_enabled

    def format(self, record):
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


def config_all_loggers(log_format_local_dev_enabled: bool):
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
        set_logging_handler(logger, fmt, log_format_local_dev_enabled)


def set_logging_handler(
    logger: logging.Logger,
    fmt: str,
    log_format_local_dev_enabled: bool,
) -> None:
    for handler in logger.handlers:
        handler.setFormatter(CustomFormatter(fmt, log_format_local_dev_enabled))


def test_logger_propagation(logger: logging.Logger):
    """log propagation and levels can sometimes be daunting to get it right.

    This function uses the `logger`` passed as argument to log the same message at different levels

    This should help to visually test a given configuration

    USAGE:
        from servicelib.logging_utils import test_logger_propagation
        for n in ("aiohttp.access", "gunicorn.access"):
            test_logger_propagation(logging.getLogger(n))
    """
    msg = f"TESTING %s log using {logger=}"
    logger.critical(msg, "critical")
    logger.error(msg, "error")
    logger.info(msg, "info")
    logger.warning(msg, "warning")
    logger.debug(msg, "debug")


def _log_arguments(
    logger_obj: logging.Logger, level: int, func: Callable, *args, **kwargs
) -> dict[str, str]:
    args_passed_in_function = [repr(a) for a in args]
    kwargs_passed_in_function = [f"{k}={v!r}" for k, v in kwargs.items()]

    # The lists of positional and keyword arguments is joined together to form final string
    formatted_arguments = ", ".join(args_passed_in_function + kwargs_passed_in_function)

    # Generate file name and function name for calling function. __func.name__ will give the name of the
    #     caller function ie. wrapper_log_info and caller file name ie log-decorator.py
    # - In order to get actual function and file name we will use 'extra' parameter.
    # - To get the file name we are using in-built module inspect.getframeinfo which returns calling file name
    py_file_caller = getframeinfo(stack()[1][0])
    extra_args = {
        "func_name_override": func.__name__,
        "file_name_override": os.path.basename(py_file_caller.filename),
    }

    #  Before to the function execution, log function details.
    logger_obj.log(
        level,
        "Arguments: %s - Begin function",
        formatted_arguments,
        extra=extra_args,
    )

    return extra_args


def log_decorator(logger=None, level: int = logging.DEBUG, log_traceback: bool = False):
    # Build logger object
    logger_obj = logger or log

    def log_decorator_info(func):
        if iscoroutinefunction(func):

            @functools.wraps(func)
            async def log_decorator_wrapper(*args, **kwargs):
                extra_args = _log_arguments(logger_obj, level, func, *args, **kwargs)
                try:
                    # log return value from the function
                    value = await func(*args, **kwargs)
                    logger_obj.log(
                        level, "Returned: - End function %r", value, extra=extra_args
                    )
                except:
                    # log exception if occurs in function
                    logger_obj.error(
                        "Exception: %s",
                        sys.exc_info()[1],
                        extra=extra_args,
                        exc_info=log_traceback,
                    )
                    raise
                # Return function value
                return value

        else:

            @functools.wraps(func)
            def log_decorator_wrapper(*args, **kwargs):
                extra_args = _log_arguments(logger_obj, level, func, *args, **kwargs)
                try:
                    # log return value from the function
                    value = func(*args, **kwargs)
                    logger_obj.log(
                        level, "Returned: - End function %r", value, extra=extra_args
                    )
                except:
                    # log exception if occurs in function
                    logger_obj.error(
                        "Exception: %s",
                        sys.exc_info()[1],
                        extra=extra_args,
                        exc_info=log_traceback,
                    )
                    raise
                # Return function value
                return value

        # Return the pointer to the function
        return log_decorator_wrapper

    return log_decorator_info


@contextmanager
def log_catch(logger: logging.Logger, reraise: bool = True):
    try:
        yield
    except asyncio.CancelledError:
        logger.debug("call was cancelled")
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Unhandled exception: %s", f"{exc}", exc_info=True)
        if reraise:
            raise exc from exc


un_capitalize = lambda s: s[:1].lower() + s[1:] if s else ""


@contextmanager
def log_context(
    logger: logging.Logger,
    level: int,
    msg: str,
    *args,
    log_duration: bool = False,
    **kwargs,
):
    # NOTE: preserves original signature https://docs.python.org/3/library/logging.html#logging.Logger.log
    start = datetime.now()  # noqa: DTZ005
    msg = un_capitalize(msg.strip())
    logger.log(level, "Starting %s ...", msg, *args, **kwargs)
    yield
    duration = (
        f" in {(datetime.now() - start ).total_seconds()}"  # noqa: DTZ005
        if log_duration
        else ""
    )
    logger.log(level, "Finished %s%s", msg, duration, *args, **kwargs)


class LogExtra(TypedDict, total=False):
    log_uid: str


def get_log_record_extra(*, user_id: int | str | None = None) -> LogExtra | None:
    extra: LogExtra = {}
    if user_id:
        assert int(user_id) > 0  # nosec
        extra["log_uid"] = f"{user_id}"
    return extra or None


LogLevelInt: TypeAlias = int
LogMessageStr: TypeAlias = str


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
