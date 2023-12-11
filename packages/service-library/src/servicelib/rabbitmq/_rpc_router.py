import asyncio
import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from models_library.rabbitmq_basic_types import RPCMethodName

from ..logging_utils import log_context
from ._errors import RPCServerError

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])

# NOTE: this is equivalent to http access logs
_logger = logging.getLogger("rpc.access")


def _create_func_msg(func, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    msg = f"{func.__name__}("

    if args_msg := ", ".join(map(str, args)):
        msg += args_msg

    if kwargs_msg := ", ".join({f"{name}={value}" for name, value in kwargs.items()}):
        if args:
            msg += ", "
        msg += kwargs_msg

    return f"{msg})"


@dataclass
class RPCRouter:
    routes: dict[RPCMethodName, Callable] = field(default_factory=dict)

    def expose(
        self,
        *,
        reraise_if_error_type: tuple[type[Exception], ...] | None = None,
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def _decorator(func: DecoratedCallable) -> DecoratedCallable:
            @functools.wraps(func)
            async def _wrapper(*args, **kwargs):

                with log_context(
                    # NOTE: this is intentionally analogous to the http access log traces.
                    # To change log-level use getLogger("rpc.access").set_level(...)
                    _logger,
                    logging.INFO,
                    msg=f"RPC call {_create_func_msg(func, args, kwargs)}",
                    log_duration=True,
                ):
                    try:
                        return await func(*args, **kwargs)

                    except asyncio.CancelledError:
                        _logger.debug("call was cancelled")
                        raise

                    except Exception as exc:  # pylint: disable=broad-except
                        if reraise_if_error_type and isinstance(
                            exc, reraise_if_error_type
                        ):
                            raise

                        _logger.exception("Unhandled exception:")
                        # NOTE: we do not return internal exceptions over RPC
                        raise RPCServerError(
                            method_name=func.__name__,
                            exc_type=f"{exc.__class__.__module__}.{exc.__class__.__name__}",
                            msg=f"{exc}",
                        ) from None

            self.routes[RPCMethodName(func.__name__)] = _wrapper
            return func

        return _decorator
