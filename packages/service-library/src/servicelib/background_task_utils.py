import datetime
import functools
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

from servicelib.exception_utils import suppress_exceptions
from servicelib.redis._errors import CouldNotAcquireLockError

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
        coro: Callable[P, Coroutine[Any, Any, None]],
    ) -> Callable[P, Coroutine[Any, Any, None]]:
        @periodic(interval=retry_after)
        @suppress_exceptions(
            # Replicas will raise CouldNotAcquireLockError
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/7574
            (CouldNotAcquireLockError,),
            reason=f"Multiple instances of the periodic task `{coro.__module__}.{coro.__name__}` are running.",
        )
        @exclusive(
            redis_client,
            lock_key=f"lock:exclusive_periodic_task:{coro.__module__}.{coro.__name__}",
        )
        @periodic(interval=task_interval)
        @functools.wraps(coro)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            return await coro(*args, **kwargs)

        return _wrapper

    return _decorator
