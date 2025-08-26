import asyncio
import logging
from typing import NoReturn

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..logging_utils import log_context

_logger = logging.getLogger(__name__)


class _ClientDisconnectedError(Exception):
    pass


async def _message_poller(
    request: Request, queue: asyncio.Queue, receive: Receive
) -> NoReturn:
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            _logger.debug(
                "client disconnected the request to %s!", request.url, stacklevel=2
            )
            raise _ClientDisconnectedError

        # Puts the message in the queue
        await queue.put(message)


async def _handler(
    app: ASGIApp, scope: Scope, queue: asyncio.Queue[Message], send: Send
) -> None:
    return await app(scope, queue.get, send)


class RequestCancellationMiddleware:
    """ASGI Middleware to cancel server requests in case of client disconnection.
    Reason: FastAPI-based (e.g. starlette) servers do not automatically cancel
    server requests in case of client disconnection. This middleware will cancel
    the server request in case of client disconnection via asyncio.CancelledError.

    WARNING: FastAPI BackgroundTasks will also get cancelled. Use with care.
    TIP: use asyncio.Task in that case
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        _logger.warning(
            "CancellationMiddleware is in use, in case of client disconection, "
            "FastAPI BackgroundTasks will be cancelled too!",
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Let's make a shared queue for the request messages
        queue: asyncio.Queue[Message] = asyncio.Queue()
        request = Request(scope)

        with log_context(_logger, logging.DEBUG, f"cancellable request {request.url}"):
            try:
                async with asyncio.TaskGroup() as tg:
                    handler_task = tg.create_task(
                        _handler(self.app, scope, queue, send)
                    )
                    poller_task = tg.create_task(
                        _message_poller(request, queue, receive)
                    )
                    await handler_task
                    poller_task.cancel()
            except* _ClientDisconnectedError:
                if not handler_task.done():
                    _logger.info(
                        "The client disconnected. The request to %s was cancelled.",
                        request.url,
                    )
