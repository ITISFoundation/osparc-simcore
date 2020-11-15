"""
This codes originates from this article (https://medium.com/swlh/add-log-decorators-to-your-python-project-84094f832181)
"""
import functools
import logging
import os
import sys
from asyncio import iscoroutinefunction
from inspect import getframeinfo, stack
from typing import Callable, Dict, Optional

from celery.app.log import Logging

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

    def format(self, record):
        if hasattr(record, "func_name_override"):
            record.funcName = record.func_name_override
        if hasattr(record, "file_name_override"):
            record.filename = record.file_name_override

        # add color
        levelname = record.levelname
        if levelname in COLORS:
            levelname_color = COLORS[levelname] + levelname + NORMAL
            record.levelname = levelname_color
        return super().format(record)


DEFAULT_FORMATTING = "%(levelname)s: [%(asctime)s/%(processName)s] [%(name)s:%(funcName)s(%(lineno)d)] %(message)s"


def config_all_logger():
    loggers = [logging.getLogger()] + [
        logging.getLogger(name) for name in logging.root.manager.loggerDict
    ]
    for logger in loggers:
        set_logging_handler(logger)


def set_logging_handler(
    logger: logging.Logger,
    formatter_base: Optional[Logging] = None,
    formatting: Optional[str] = None,
) -> None:
    if not formatting:
        formatting = DEFAULT_FORMATTING
    if not formatter_base:
        formatter_base = CustomFormatter

    for handler in logger.handlers:
        handler.setFormatter(
            formatter_base(
                "%(levelname)s: %(name)s:%(funcName)s(%(lineno)s) - %(message)s"
            )
        )


def _log_arguments(
    logger_obj: logging.Logger, func: Callable, *args, **kwargs
) -> Dict[str, str]:
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
    logger_obj.info(
        "Arguments: %s - Begin function",
        formatted_arguments,
        extra=extra_args,
    )

    return extra_args


def log_decorator(logger=None):
    # Build logger object
    logger_obj = logger or log

    def log_decorator_info(func):
        if iscoroutinefunction(func):

            @functools.wraps(func)
            async def log_decorator_wrapper(*args, **kwargs):
                extra_args = _log_arguments(logger_obj, func, *args, **kwargs)
                try:
                    # log return value from the function
                    value = await func(*args, **kwargs)
                    logger_obj.debug(
                        "Returned: - End function %r", value, extra=extra_args
                    )
                except:
                    # log exception if occurs in function
                    logger_obj.error(
                        "Exception: %s", sys.exc_info()[1], extra=extra_args
                    )
                    raise
                # Return function value
                return value

        else:

            @functools.wraps(func)
            def log_decorator_wrapper(*args, **kwargs):
                extra_args = _log_arguments(logger_obj, func, *args, **kwargs)
                try:
                    # log return value from the function
                    value = func(*args, **kwargs)
                    logger_obj.debug(
                        "Returned: - End function %r", value, extra=extra_args
                    )
                except:
                    # log exception if occurs in function
                    logger_obj.error(
                        "Exception: %s", sys.exc_info()[1], extra=extra_args
                    )
                    raise
                # Return function value
                return value

        # Return the pointer to the function
        return log_decorator_wrapper

    return log_decorator_info
