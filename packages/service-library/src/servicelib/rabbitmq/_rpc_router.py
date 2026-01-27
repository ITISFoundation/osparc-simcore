import asyncio
import functools
import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from common_library.error_codes import create_error_code
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from models_library.rabbitmq_basic_types import RPCMethodName

from ..logging_utils import log_context
from ._errors import RPCServerError

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])


_logger = logging.getLogger(
    # NOTE: this logger is equivalent to http access logs
    "rpc.access"
)


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
                        _logger.debug("Call %s was cancelled", func.__name__)
                        raise

                    except Exception as exc:  # pylint: disable=broad-except
                        if reraise_if_error_type and isinstance(exc, reraise_if_error_type):
                            raise

                        error_code = create_error_code(exc)
                        _logger.exception(
                            # NOTE: equivalent to a 500 http status code error
                            **create_troubleshooting_log_kwargs(
                                f"Unhandled exception on the rpc-server side for '{func.__name__}'",
                                error=exc,
                                error_code=error_code,
                                error_context={
                                    "rpc_method": func.__name__,
                                    "args": args,
                                    "kwargs": kwargs,
                                },
                            )
                        )
                        # NOTE: we do not return internal exceptions over RPC
                        formatted_traceback = "\n".join(traceback.format_tb(exc.__traceback__))
                        raise RPCServerError(
                            method_name=func.__name__,
                            exc_type=f"{exc.__class__.__module__}.{exc.__class__.__name__}",
                            exc_message=f"{exc}",
                            traceback=f"{formatted_traceback}",
                            error_code=error_code,
                        ) from None

            self.routes[RPCMethodName(func.__name__)] = _wrapper
            return func

        return _decorator
