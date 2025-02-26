import asyncio
import functools
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

R = TypeVar("R")


def make_async(
    executor=None,
) -> Callable[[Callable[..., R]], Callable[..., Coroutine[Any, Any, R]]]:
    def decorator(func) -> Callable[..., Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> R:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                executor, functools.partial(func, *args, **kwargs)
            )

        return wrapper

    return decorator
