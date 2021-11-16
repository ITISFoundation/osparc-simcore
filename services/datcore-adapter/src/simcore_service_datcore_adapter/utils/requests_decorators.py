import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress
from functools import wraps
from typing import Any, Callable, Coroutine, Optional

from fastapi import Request, Response

logger = logging.getLogger(__name__)

_DEFAULT_CHECK_INTERVAL_S: float = 0.5


async def _cancel_task_if_client_disconnected(
    request: Request, task: asyncio.Task, interval: float = _DEFAULT_CHECK_INTERVAL_S
) -> None:
    try:
        while True:
            if task.done():
                logger.debug("task %s is done", task)
                break
            if await request.is_disconnected():
                logger.warning("client %s disconnected!", request.client)
                task.cancel()
                break
            await asyncio.sleep(interval)
    except CancelledError:
        logger.debug("task was cancelled")
        raise
    finally:
        logger.debug("task completed")


def cancellable_request(handler: Callable[..., Coroutine[Any, Any, Optional[Any]]]):
    """this decorator periodically checks if the client disconnected and then will cancel the request and return a 499 code (a la nginx).
    Usage:

    decorate the cancellable route and add request: Request as an argument

    @cancellable_request
    async def route(
        _request: Request,
        ...
    )
    """

    @wraps(handler)
    async def decorator(*args, **kwargs) -> Optional[Any]:
        request = kwargs["_request"]
        handler_task = asyncio.create_task(
            handler(*args, **kwargs), name="cancellable_request/handler"
        )
        auto_cancel_task = asyncio.create_task(
            _cancel_task_if_client_disconnected(request, handler_task),
            name="cancellable_request/auto_cancel",
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
            with suppress(CancelledError):
                await auto_cancel_task

    return decorator
