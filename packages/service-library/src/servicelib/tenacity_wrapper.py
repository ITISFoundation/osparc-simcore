import logging
import sys
from typing import Any, Callable, Dict, Union

from tenacity import RetryCallState
from tenacity import Retrying as TenacityRetrying
from tenacity import WrappedFn
from tenacity import retry as tenacity_retry
from tenacity._asyncio import AsyncRetrying as TenacityAsyncRetrying
from tenacity.after import after_log
from tenacity.before import before_log

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def _get_before_logger() -> Callable[[RetryCallState], None]:
    return before_log(logger, logging.DEBUG)


def _get_after_logger() -> Callable[[RetryCallState], None]:
    return after_log(logger, logging.DEBUG)


def _inject_loggers_if_missing(kwargs: Dict[str, Any]) -> None:
    if "before" not in kwargs:
        kwargs["before"] = _get_before_logger()
    if "after" not in kwargs:
        kwargs["after"] = _get_after_logger()


class AsyncRetrying(TenacityAsyncRetrying):
    def __init__(self, **kwargs: Any) -> None:
        _inject_loggers_if_missing(kwargs)
        super().__init__(**kwargs)


class Retrying(TenacityRetrying):
    def __init__(self, **kwargs: Any):
        _inject_loggers_if_missing(kwargs)
        super().__init__(**kwargs)


def retry(
    *dargs: Any, **dkw: Any
) -> Union[WrappedFn, Callable[[WrappedFn], WrappedFn]]:
    _inject_loggers_if_missing(dkw)
    return tenacity_retry(*dargs, **dkw)


__all__ = ["AsyncRetrying", "Retrying", "retry"]
