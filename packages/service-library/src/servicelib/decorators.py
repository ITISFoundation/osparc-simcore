""" General purpose decorators

IMPORTANT: lowest level module
   I order to avoid cyclic dependences, please
   DO NOT IMPORT ANYTHING from .
"""

import asyncio
import datetime
import logging
from collections.abc import Callable, Coroutine
from copy import deepcopy
from functools import wraps
from typing import Any

_logger = logging.getLogger(__name__)


def safe_return(if_fails_return=False, catch=None, logger=None):  # noqa: FBT002
    # defaults
    if catch is None:
        catch = (RuntimeError,)
    if logger is None:
        logger = _logger

    def decorate(func):
        @wraps(func)
        def safe_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except catch as err:
                logger.info("%s failed:  %s", func.__name__, str(err))
            except Exception:  # pylint: disable=broad-except
                logger.info("%s failed unexpectedly", func.__name__, exc_info=True)
            return deepcopy(if_fails_return)  # avoid issues with default mutable

        return safe_func

    return decorate


def async_delayed(
    interval: datetime.timedelta,
) -> Callable[..., Callable[..., Coroutine]]:
    def decorator(func) -> Callable[..., Coroutine]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            await asyncio.sleep(interval.total_seconds())
            return await func(*args, **kwargs)

        return wrapper

    return decorator
