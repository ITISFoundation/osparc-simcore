import asyncio
import logging
from functools import partial

from servicelib.async_utils import TaskCancelled, run_until_cancelled
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..logging_utils import log_context

_logger = logging.getLogger(__name__)


async def _handler(
    app: ASGIApp, scope: Scope, queue: asyncio.Queue[Message], send: Send
) -> None:
    await app(scope, queue.get, send)


async def _is_client_disconnected(
    receive: Receive, queue: asyncio.Queue[Message], request: Request
) -> bool:
    message = await receive()
    if message["type"] == "http.disconnect":
        _logger.debug("client disconnected, terminating request to %s!", request.url)
        return True

    # Puts the message in the queue
    await queue.put(message)
    return False


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
        request = Request(scope)
        queue: asyncio.Queue[Message] = asyncio.Queue()

        with log_context(_logger, logging.DEBUG, f"cancellable request {request.url}"):
            try:
                await run_until_cancelled(
                    coro=_handler(self.app, scope, queue, send),
                    cancel_callback=partial(
                        _is_client_disconnected, receive, queue, request
                    ),
                    poll_interval=0.0,
                )
                return

            except TaskCancelled:
                _logger.info(
                    "The client disconnected. request to %s was cancelled.",
                    request.url,
                )
