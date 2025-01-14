import datetime
import functools
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

from .background_task import periodic
from .redis import RedisClientSDK, exclusive

P = ParamSpec("P")
R = TypeVar("R")


def exclusive_periodic(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    task_interval: datetime.timedelta,
    retry_after: datetime.timedelta = datetime.timedelta(seconds=1),
) -> Callable[
    [Callable[P, Coroutine[Any, Any, None]]], Callable[P, Coroutine[Any, Any, None]]
]:
    """decorates a function to become exclusive and periodic.

    Arguments:
        client -- The Redis client
        task_interval -- the task interval, i.e. how often the task should run
        retry_after -- in case the exclusive lock cannot be acquired or is lost, this is the retry interval

    Raises:
        Nothing

    Returns:
        Nothing, a periodic method does not return anything as it runs forever.
    """

    def _decorator(
        func: Callable[P, Coroutine[Any, Any, None]],
    ) -> Callable[P, Coroutine[Any, Any, None]]:
        @periodic(interval=retry_after)
        @exclusive(
            redis_client,
            lock_key=f"lock:exclusive_periodic_task:{func.__name__}",
        )
        @periodic(interval=task_interval)
        @functools.wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            return await func(*args, **kwargs)

        return _wrapper

    return _decorator
