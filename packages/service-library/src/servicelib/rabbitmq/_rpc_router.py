import asyncio
import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import SecretStr

from ..logging_utils import log_context
from ._errors import RPCServerError
from ._models import RPCMethodName

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])

_logger = logging.getLogger("rpc.access")

_RPC_CUSTOM_ENCODER: dict[Any, Callable[[Any], Any]] = {
    SecretStr: SecretStr.get_secret_value
}


@dataclass
class RPCRouter:
    routes: dict[RPCMethodName, Callable] = field(default_factory=dict)

    def expose(self) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                with log_context(
                    _logger,
                    logging.INFO,
                    msg=f"calling {func.__name__} with {args}, {kwargs}",
                ):
                    try:
                        return await func(*args, **kwargs)
                    except asyncio.CancelledError:
                        _logger.debug("call was cancelled")
                        raise
                    except Exception as exc:  # pylint: disable=broad-except
                        _logger.exception("Unhandled exception:")
                        # NOTE: we do not return internal exceptions over RPC
                        raise RPCServerError(
                            method_name=func.__name__,
                            exc_type=f"{type(exc)}",
                            msg=f"{exc}",
                        ) from None

            self.routes[RPCMethodName(func.__name__)] = wrapper
            return func

        return decorator
