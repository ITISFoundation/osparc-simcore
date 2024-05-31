import asyncio
import logging
from collections.abc import Callable, Coroutine
from contextlib import suppress
from functools import wraps
from typing import Any

from fastapi import Request, Response

_logger = logging.getLogger(__name__)

_DEFAULT_CHECK_INTERVAL_S: float = 0.5


async def _cancel_task_if_client_disconnected(
    request: Request, task: asyncio.Task, interval: float = _DEFAULT_CHECK_INTERVAL_S
) -> None:
    with suppress(asyncio.CancelledError):
        while True:
            if await request.is_disconnected():
                _logger.warning("client %s disconnected!", request.client)
                task.cancel()
                break
            await asyncio.sleep(interval)


def cancellable_request(handler: Callable[..., Coroutine[Any, Any, Any]]):
    """this decorator periodically checks if the client disconnected and then will cancel the request and return a 499 code (a la nginx)."""

    @wraps(handler)
    async def decorator(request: Request, *args, **kwargs) -> Response:
        handler_task = asyncio.get_event_loop().create_task(
            handler(request, *args, **kwargs)
        )
        auto_cancel_task = asyncio.get_event_loop().create_task(
            _cancel_task_if_client_disconnected(request, handler_task)
        )
        try:
            return await handler_task
        except asyncio.CancelledError:
            _logger.warning(
                "request %s was cancelled by client %s!", request.url, request.client
            )
            return Response("Oh No!", status_code=499)
        finally:
            auto_cancel_task.cancel()

    return decorator
