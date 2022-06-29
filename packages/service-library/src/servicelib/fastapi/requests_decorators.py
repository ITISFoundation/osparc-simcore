import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress
from functools import wraps
from typing import Any, Callable, Coroutine, Optional

from fastapi import Request, Response

logger = logging.getLogger(__name__)

_DEFAULT_CHECK_INTERVAL_S: float = 0.5

HTTP_499_CLIENT_CLOSED_REQUEST = 499
# A non-standard status code introduced by nginx for the case when a client
# closes the connection while nginx is processing the request.
# SEE https://www.webfx.com/web-development/glossary/http-status-codes/what-is-a-499-status-code/

_FastAPIHandlerCallable = Callable[..., Coroutine[Any, Any, Optional[Any]]]


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


def cancellable_request(handler_fun: _FastAPIHandlerCallable):
    """This decorator periodically checks if the client disconnected and
    then will cancel the request and return a HTTP_499_CLIENT_CLOSED_REQUEST code (a la nginx).

    Usage: decorate the cancellable route and add request: Request as an argument

        @cancellable_request
        async def route(
            _request: Request,
            ...
        )
    """

    @wraps(handler_fun)
    async def wrapper(*args, **kwargs) -> Optional[Any]:
        request: Request = kwargs["_request"]

        # Intercepts handler call and creates a task out of it
        handler_task = asyncio.create_task(
            handler_fun(*args, **kwargs),
            name=f"cancellable_request/handler/{handler_fun.__name__}",
        )
        # An extra task to monitor when the client disconnects so it can
        # cancel 'handler_task'
        auto_cancel_task = asyncio.create_task(
            _cancel_task_if_client_disconnected(request, handler_task),
            name=f"cancellable_request/auto_cancel/{handler_fun.__name__}",
        )

        try:
            return await handler_task
        except CancelledError:
            logger.warning(
                "Request %s was cancelled since client %s disconnected !",
                f"{request.url}",
                request.client,
            )
            return Response(
                "Request cancelled because client disconnected",
                status_code=HTTP_499_CLIENT_CLOSED_REQUEST,
            )
        finally:
            # TODO: is this called when return ??? Should it stop when responded?
            auto_cancel_task.cancel()
            with suppress(CancelledError):
                await auto_cancel_task

    return wrapper
