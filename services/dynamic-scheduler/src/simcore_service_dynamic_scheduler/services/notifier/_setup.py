from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from . import _notifier, _socketio


@asynccontextmanager
async def lifespan_notifier(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(_socketio.lifespan(app))
        await stack.enter_async_context(_notifier.lifespan(app))

        yield
