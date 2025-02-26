import asyncio
import logging

from servicelib.logging_utils import log_context
from starlette.types import ASGIApp, Receive, Scope, Send

_logger = logging.getLogger(__name__)


class _TerminateTaskGroupError(Exception):
    pass


async def _message_poller(queue, receive):
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            raise _TerminateTaskGroupError

        # Puts the message in the queue
        await queue.put(message)


async def _handler(app: ASGIApp, scope: Scope, queue: asyncio.Queue, send: Send):
    return await app(scope, queue.get, send)


class CancellationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return None

        # Let's make a shared queue for the request messages
        queue = asyncio.Queue()

        with log_context(_logger, logging.DEBUG, f"cancellable request {scope}"):
            try:
                async with asyncio.TaskGroup() as tg:
                    handler_task = tg.create_task(
                        _handler(self.app, scope, queue, send)
                    )
                    poller_task = tg.create_task(_message_poller(queue, receive))
                    response = await handler_task
                    poller_task.cancel()
                    return response
            except* _TerminateTaskGroupError:
                _logger.info("The client disconnected. The task group was cancelled.")
