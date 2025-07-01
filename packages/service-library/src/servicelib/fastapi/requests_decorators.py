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

    async def __call__(self, request: Request, *args: Any, **kwargs: Any) -> Any: ...


def _validate_signature(handler: _HandlerWithRequestArg):
    """Raises ValueError if handler does not have expected signature"""
    try:
        p = next(iter(inspect.signature(handler).parameters.values()))
        if p.kind != inspect.Parameter.POSITIONAL_OR_KEYWORD or p.annotation != Request:
            msg = f"Invalid handler {handler.__name__} signature: first parameter must be a Request, got {p.annotation}"
            raise TypeError(msg)
    except StopIteration as e:
        msg = f"Invalid handler {handler.__name__} signature: first parameter must be a Request, got none"
        raise TypeError(msg) from e


#
# cancel_on_disconnect based on TaskGroup
#
_POLL_INTERVAL_S: float = 0.01


class _ClientDisconnectedError(Exception):
    """Internal exception raised by the poller task when the client disconnects."""


async def _disconnect_poller_for_task_group(
    close_event: asyncio.Event, request: Request
):
    """
    Polls for client disconnection and raises _ClientDisconnectedError if it occurs.
    """
    while not await request.is_disconnected():
        await asyncio.sleep(_POLL_INTERVAL_S)
        if close_event.is_set():
            return
    raise _ClientDisconnectedError()


def cancel_on_disconnect(handler: _HandlerWithRequestArg):
    """
    Decorator that cancels the request handler if the client disconnects.

    Uses a TaskGroup to manage the handler and a poller task concurrently.
    If the client disconnects, the poller raises an exception, which is
    caught and translated into a 503 Service Unavailable response.
    """

    _validate_signature(handler)

    @wraps(handler)
    async def wrapper(request: Request, *args, **kwargs):
        sentinel = object()
        kill_poller_task_event = asyncio.Event()
        try:
            async with asyncio.TaskGroup() as tg:

                tg.create_task(
                    _disconnect_poller_for_task_group(kill_poller_task_event, request),
                    name=f"cancel_on_disconnect/poller/{handler.__name__}/{id(sentinel)}",
                )
                handler_task = tg.create_task(
                    handler(request, *args, **kwargs),
                    name=f"cancel_on_disconnect/handler/{handler.__name__}/{id(sentinel)}",
                )
                await handler_task
                kill_poller_task_event.set()

            return handler_task.result()

        except* _ClientDisconnectedError as eg:
            logger.info(
                "Request %s %s cancelled since client %s disconnected.",
                request.method,
                request.url,
                request.client,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Client disconnected",
            ) from eg

        except* Exception as eg:
            raise eg.exceptions[0]

    return wrapper


__all__: tuple[str, ...] = ("cancel_on_disconnect",)
