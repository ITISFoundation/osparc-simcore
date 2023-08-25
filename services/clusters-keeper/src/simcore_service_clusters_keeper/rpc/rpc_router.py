import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from servicelib.logging_utils import log_catch, log_context

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])

_logger = logging.getLogger(__name__)


@dataclass
class RPCRouter:
    routes: dict[str, Callable] = field(default_factory=dict)

    def expose(self) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                with log_context(
                    _logger,
                    logging.INFO,
                    msg=f"calling {func.__name__} with {args}, {kwargs}",
                ), log_catch(_logger, reraise=True):
                    return await func(*args, **kwargs)

            self.routes[func.__name__] = wrapper
            return func

        return decorator
