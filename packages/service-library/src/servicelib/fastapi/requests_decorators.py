import asyncio
import inspect
import logging
from functools import wraps
from typing import Any, Protocol

from fastapi import Request, status
from fastapi.exceptions import HTTPException

logger = logging.getLogger(__name__)


class _HandlerWithRequestArg(Protocol):
    __name__: str

    async def __call__(self, request: Request, *args: Any) -> Any:
        ...


def _validate_signature(handler: _HandlerWithRequestArg):
    """Raises ValueError if handler does not have expected signature"""
    try:
        p = next(iter(inspect.signature(handler).parameters.values()))
        if p.kind != inspect.Parameter.POSITIONAL_OR_KEYWORD or p.annotation != Request:
            raise TypeError(
                f"Invalid handler {handler.__name__} signature: first parameter must be a Request, got {p.annotation}"
            )
    except StopIteration as e:
        raise TypeError(
            f"Invalid handler {handler.__name__} signature: first parameter must be a Request, got none"
        ) from e


#
# cancel_on_disconnect/disconnect_poller based
# on https://github.com/RedRoserade/fastapi-disconnect-example/blob/main/app.py
#
_POLL_INTERVAL_S: float = 0.01


async def disconnect_poller(request: Request, result: Any):
    """
    Poll for a disconnect.
    If the request disconnects, stop polling and return.
    """
    while not await request.is_disconnected():
        await asyncio.sleep(_POLL_INTERVAL_S)

    logger.debug(
        "client %s disconnected! Cancelling handler for request %s %s",
        request.client,
        request.method,
        request.url,
    )
    return result


def cancel_on_disconnect(handler: _HandlerWithRequestArg):
    """
    After client dicsonnects, handler gets cancelled in ~<3 secs
    """

    _validate_signature(handler)

    @wraps(handler)
    async def wrapper(request: Request, *args, **kwargs):
        sentinel = object()

        # Create two tasks:
        # one to poll the request and check if the client disconnected
        poller_task = asyncio.create_task(
            disconnect_poller(request, sentinel),
            name=f"cancel_on_disconnect/poller/{handler.__name__}/{id(sentinel)}",
        )
        # , and another which is the request handler
        handler_task = asyncio.create_task(
            handler(request, *args, **kwargs),
            name=f"cancel_on_disconnect/handler/{handler.__name__}/{id(sentinel)}",
        )

        done, pending = await asyncio.wait(
            [poller_task, handler_task], return_when=asyncio.FIRST_COMPLETED
        )

        # One has completed, cancel the other
        for t in pending:
            t.cancel()
            try:
                await asyncio.wait_for(t, timeout=3)
            except asyncio.CancelledError:
                logger.debug("%s was cancelled", t)
            except Exception as exc:  # pylint: disable=broad-except
                if t is handler_task:
                    logger.warning(
                        "%s raised %s when being cancelled.", t, exc, exc_info=True
                    )
                    raise
            finally:
                assert t.done()  # nosec

        # Return the result if the handler finished first
        if handler_task in done:
            assert poller_task.done()  # nosec
            return await handler_task

        # Otherwise, raise an exception. This is not exactly needed, but it will prevent
        # validation errors if your request handler is supposed to return something.
        logger.debug(
            "Request %s %s cancelled:\n - %s\n - %s",
            request.method,
            request.url,
            f"{poller_task=}",
            f"{handler_task=}",
        )
        assert poller_task.done()  # nosec
        assert handler_task.done()  # nosec

        # NOTE: uvicorn server fails with 499
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"client disconnected from {request=}",
        )

    return wrapper
