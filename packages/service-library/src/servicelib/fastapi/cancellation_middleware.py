import asyncio
import functools
import logging

from fastapi import Request, Response
from servicelib.logging_utils import log_context
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import ASGIApp, Receive, Scope, Send

_logger = logging.getLogger(__name__)


class _TerminateTaskGroupError(Exception):
    pass


async def _client_disconnected(request: Request) -> None:
    while not await request.is_disconnected():  # noqa: ASYNC110
        await asyncio.sleep(0.01)
    _logger.info("Client disconnected! Terminating task group!")
    raise _TerminateTaskGroupError


async def _handler(request: Request, call_next: RequestResponseEndpoint) -> Response:
    try:
        return await call_next(request)
    except asyncio.CancelledError:
        _logger.info("Handler was cancelled")
        raise


async def cancellation_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    sentinel = object()
    call_id = id(sentinel)

    with log_context(_logger, logging.DEBUG, f"cancellable request {request.url}"):
        try:
            async with asyncio.TaskGroup() as tg:
                monitoring_task = tg.create_task(
                    _client_disconnected(request),
                    name=f"client_connection_monitoring/poller/{request.url}/{call_id}",
                )
                handler_task = tg.create_task(
                    _handler(request, call_next),
                    name=f"handler/{request.url}/{call_id}",
                )
                response = await handler_task
                monitoring_task.cancel()
                return response
        except _TerminateTaskGroupError:
            _logger.info("The client disconnected. The task group was cancelled.")
            handler_task.cancel()
    return Response(status_code=499, content="Client disconnected")


def cancellation_middleware2():
    def _decorator(app):
        @functools.wraps(app)
        async def _wrapped_app(scope, receive, send):
            await app(scope, receive, send)

        return _wrapped_app

    return _decorator


class CancellationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return None

        # Let's make a shared queue for the request messages
        queue = asyncio.Queue()

        async def message_poller(sentinel, handler_task):
            nonlocal queue
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    handler_task.cancel()
                    return sentinel  # Break the loop

                # Puts the message in the queue
                await queue.put(message)

        sentinel = object()
        async with asyncio.TaskGroup() as tg:
            handler_task = tg.create_task(self.app(scope, queue.get, send))
            poller_task = tg.create_task(message_poller(sentinel, handler_task))

        try:
            return await handler_task
        except asyncio.CancelledError:
            _logger.info("Cancelling request due to disconnect")
