import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress
from functools import wraps
from typing import Any, Callable, Coroutine, Optional

from fastapi import Depends, Request, Response

logger = logging.getLogger(__name__)

_DEFAULT_CHECK_INTERVAL_S: float = 0.5


async def _cancel_task_if_client_disconnected(
    request: Request, task: asyncio.Task, interval: float = _DEFAULT_CHECK_INTERVAL_S
) -> None:
    with suppress(CancelledError):
        while True:
            if await request.is_disconnected():
                logger.warning("client %s disconnected!", request.client)
                task.cancel()
                break
            await asyncio.sleep(interval)


def cancellable_request(handler: Callable[[Any], Coroutine[Any, Any, Optional[Any]]]):
    """this decorator periodically checks if the client disconnected and then will cancel the request and return a 499 code (a la nginx).
    Usage:

    decorate the cancellable route and add request: Request as an argument

    @cancellable_request
    async def route(
        request: Request,  # pylint:disable=unused-argument
        ...
    )
    """

    @wraps(handler)
    async def decorator(request: Request, *args, **kwargs) -> Optional[Any]:
        handler_task = asyncio.get_event_loop().create_task(
            handler(request, *args, **kwargs)
        )
        auto_cancel_task = asyncio.get_event_loop().create_task(
            _cancel_task_if_client_disconnected(request, handler_task)
        )
        try:
            return await handler_task
        except CancelledError:
            logger.warning(
                "request %s was cancelled by client %s!", request.url, request.client
            )
            return Response("Oh No!", status_code=499)
        finally:
            auto_cancel_task.cancel()

    return decorator
