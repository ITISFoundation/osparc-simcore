from collections.abc import AsyncGenerator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncContextManager, TypeAlias

from fastapi import FastAPI

LifespanContextManager: TypeAlias = Callable[[FastAPI], AsyncContextManager[None]]


def combine_lfiespan_context_managers(
    *context_managers: LifespanContextManager,
) -> LifespanContextManager:
    """the first entry has its `setup` called first and its `teardown` called last
    With `setup` and `teardown` referring to the code before and after the `yield`
    """

    @asynccontextmanager
    async def _(app: FastAPI) -> AsyncGenerator[None, None]:
        async with AsyncExitStack() as stack:
            for context_manager in context_managers:
                await stack.enter_async_context(context_manager(app))
            yield

    return _
