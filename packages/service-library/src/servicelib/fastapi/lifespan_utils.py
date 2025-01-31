from collections.abc import AsyncGenerator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncContextManager, TypeAlias

from fastapi import FastAPI

LifespanContextManager: TypeAlias = Callable[[FastAPI], AsyncContextManager[None]]


def combine_lfiespans(*lifespans: LifespanContextManager) -> LifespanContextManager:
    """Applyes the `setup` part of the context mangers in the order they are provided.
    The `teardown` is in revere order with regarad to the `seutp`.
    """

    @asynccontextmanager
    async def _(app: FastAPI) -> AsyncGenerator[None, None]:
        async with AsyncExitStack() as stack:
            for context_manager in lifespans:
                await stack.enter_async_context(context_manager(app))
            yield

    return _
