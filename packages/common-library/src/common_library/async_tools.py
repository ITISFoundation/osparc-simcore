import asyncio
import functools
from collections.abc import Awaitable, Callable
from concurrent.futures import Executor
from typing import ParamSpec, TypeVar

R = TypeVar("R")
P = ParamSpec("P")


def make_async(
    executor: Executor | None = None,
) -> Callable[[Callable[P, R]], Callable[P, Awaitable[R]]]:
    def decorator(func: Callable[P, R]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(
                    executor, functools.partial(func, *args, **kwargs)
                ),
                timeout=2,
            )  # wait_for is temporary for debugging async jobs

        return wrapper

    return decorator
