import logging
import sys
import typing
from typing import Any, Callable, Dict, Union

from tenacity import RetryCallState
from tenacity import Retrying as TenacityRetrying
from tenacity import WrappedFn
from tenacity import retry as tenacity_retry
from tenacity._asyncio import AsyncRetrying as TenacityAsyncRetrying
from tenacity.after import after_log
from tenacity.before import before_log

if typing.TYPE_CHECKING:
    import types

    from tenacity.stop import stop_base
    from tenacity.wait import wait_base


logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def _get_before_logger() -> Callable[[RetryCallState], None]:
    return before_log(logger, logging.DEBUG)


def _get_after_logger() -> Callable[[RetryCallState], None]:
    return after_log(logger, logging.DEBUG)


def _inject_in_kwargs(kwargs: Dict[str, Any]) -> None:
    if "before" not in kwargs:
        kwargs["before"] = _get_before_logger()
    if "after" not in kwargs:
        kwargs["after"] = _get_after_logger()


class AsyncRetrying(TenacityAsyncRetrying):
    def __init__(self, **kwargs: Any) -> None:
        _inject_in_kwargs(kwargs)
        super().__init__(**kwargs)


class Retrying(TenacityRetrying):
    def __init__(self, **kwargs: Any):
        _inject_in_kwargs(kwargs)
        super().__init__(**kwargs)


def retry(
    *dargs: Any, **dkw: Any
) -> Union[WrappedFn, Callable[[WrappedFn], WrappedFn]]:
    _inject_in_kwargs(dkw)
    return tenacity_retry(*dargs, **dkw)


__all__ = ["AsyncRetrying", "Retrying", "retry"]
