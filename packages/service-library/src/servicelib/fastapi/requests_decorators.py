import asyncio
import inspect
import logging
from asyncio import CancelledError
from contextlib import suppress
from functools import wraps
from typing import Any, Callable, Coroutine, Optional

from fastapi import Request, Response, status
from fastapi.exceptions import HTTPException

logger = logging.getLogger(__name__)


_DEFAULT_CHECK_INTERVAL_S: float = 0.01

HTTP_499_CLIENT_CLOSED_REQUEST = 499
# A non-standard status code introduced by nginx for the case when a client
# closes the connection while nginx is processing the request.
# SEE https://www.webfx.com/web-development/glossary/http-status-codes/what-is-a-499-status-code/

TASK_NAME_PREFIX = "cancellable_request"

_Handler = Callable[[Request, Any], Coroutine[Any, Any, Optional[Any]]]


def _validate_signature(handler: _Handler):
    """Raises ValueError if handler does not have expected signature"""
    # IMPROVEMENT: inject this parameter to handler_fun here before it returned in the wrapper and consumed by fastapi.router?
    if not any(
        parameter.name == "request" and parameter.annotation == Request
        for parameter in inspect.signature(handler).parameters.values()
    ):
        raise ValueError(
            f"Invalid handler {handler.__name__} signature: missing required parameter _request: Request"
        )


async def _cancel_task_if_client_disconnected(
    request: Request, task: asyncio.Task, interval: float = _DEFAULT_CHECK_INTERVAL_S
) -> None:
    try:
        while True:
            if task.done():
                logger.debug("task %s is done", task)
                break
            if await request.is_disconnected():
                logger.warning(
                    "client %s disconnected! Cancelling handler for %s",
                    request.client,
                    f"{request.url=}",
                )
                task.cancel()
                break
            await asyncio.sleep(interval)
    except CancelledError:
        logger.debug("task monitoring %s handler was cancelled", f"{request.url=}")
        raise
    finally:
        logger.debug("task monitoring %s handler completed", f"{request.url}")


def cancellable_request(handler: _Handler):
    """This decorator periodically checks if the client disconnected and
    then will cancel the request and return a HTTP_499_CLIENT_CLOSED_REQUEST code (a la nginx).

    Usage: decorate the cancellable route and add request: Request as an argument

        @cancellable_request
        async def route(
            _request: Request,
            ...
        )
    """

    _validate_signature(handler)

    # WRAPPER ----
    @wraps(handler)
    async def wrapper(request: Request, *args, **kwargs) -> Optional[Any]:

        # Intercepts handler call and creates a task out of it
        handler_task = asyncio.create_task(
            handler(request, *args, **kwargs),
            name=f"{TASK_NAME_PREFIX}/handler/{handler.__name__}",
        )
        # An extra task to monitor when the client disconnects so it can
        # cancel 'handler_task'
        auto_cancel_task = asyncio.create_task(
            _cancel_task_if_client_disconnected(request, handler_task),
            name=f"{TASK_NAME_PREFIX}/auto_cancel/{handler.__name__}",
        )

        try:
            return await handler_task
        except CancelledError:
            # TODO: check that 'auto_cancel_task' actually executed this cancellation
            # E.g. app shutdown might cancel all pending tasks
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
            # NOTE: This is ALSO called 'await handler_task' returns
            auto_cancel_task.cancel()
            with suppress(CancelledError):
                await auto_cancel_task

    return wrapper


#
# Based on https://github.com/RedRoserade/fastapi-disconnect-example/blob/main/app.py
#


async def disconnect_poller(request: Request, result: Any):
    """
    Poll for a disconnect.
    If the request disconnects, stop polling and return.
    """
    while not await request.is_disconnected():
        await asyncio.sleep(_DEFAULT_CHECK_INTERVAL_S)

    logger.debug(
        "client %s disconnected! Cancelling handler for request %s %s",
        request.client,
        request.method,
        request.url,
    )
    return result


def cancel_on_disconnect(handler: _Handler):

    try:
        first_parameter = next(iter(inspect.signature(handler).parameters.values()))
        if not first_parameter.annotation == Request:
            raise TypeError(
                f"Invalid handler {handler.__name__} signature: first parameter must be a Request, got {first_parameter.annotation}"
            )
    except StopIteration as e:
        raise TypeError(
            f"Invalid handler {handler.__name__} signature: first parameter must be a Request, got none"
        ) from e

    @wraps(handler)
    async def wrapper(request: Request, *args, **kwargs):
        sentinel = object()

        # Create two tasks:
        # one to poll the request and check if the client disconnected
        poller_task = asyncio.create_task(
            disconnect_poller(request, sentinel),
            name=f"{TASK_NAME_PREFIX}/poller/{handler.__name__}",
        )
        # , and another which is the request handler
        handler_task = asyncio.create_task(
            handler(request, *args, **kwargs),
            name=f"{TASK_NAME_PREFIX}/handler/{handler.__name__}",
        )

        done, pending = await asyncio.wait(
            [poller_task, handler_task], return_when=asyncio.FIRST_COMPLETED
        )

        # One has completed, cancel the other
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                logger.debug("%s was cancelled", t)
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("%s raised %s when being cancelled", t, exc)

        # Return the result if the handler finished first
        if handler_task in done:
            return await handler_task

        # Otherwise, raise an exception
        # This is not exactly needed, but it will prevent
        # validation errors if your request handler is supposed
        # to return something.
        logger.debug(
            "Request %s %s cancelled.",
            request.method,
            request.url,
        )

        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    return wrapper
