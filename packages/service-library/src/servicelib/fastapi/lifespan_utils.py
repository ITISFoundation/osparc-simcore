from collections.abc import AsyncGenerator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncContextManager, TypeAlias

from fastapi import FastAPI

LifespanContextManager: TypeAlias = Callable[[FastAPI], AsyncContextManager[None]]


def combine_lifespans(*lifespans: LifespanContextManager) -> LifespanContextManager:
    """Applies the `setup` part of the contextmangers in the order they are provided.
    The `teardown` is run in reverse order with regard to the `setup`.
    """

    @asynccontextmanager
    async def _(app: FastAPI) -> AsyncGenerator[None, None]:
        async with AsyncExitStack() as stack:
            for lifespan in lifespans:
                await stack.enter_async_context(lifespan(app))
            yield

    return _
