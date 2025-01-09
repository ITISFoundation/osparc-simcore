import asyncio
import datetime
import logging
from collections.abc import Awaitable, Callable

import arrow

from ..background_task import periodic
from ._client import RedisClientSDK
from ._decorators import exclusive

_logger = logging.getLogger(__name__)


def start_exclusive_periodic_task(
    client: RedisClientSDK,
    task: Callable[..., Awaitable[None]],
    *,
    task_period: datetime.timedelta,
    retry_after: datetime.timedelta = datetime.timedelta(seconds=1),
    task_name: str,
    **kwargs,
) -> asyncio.Task:
    """
    Ensures that only 1 process periodically ever runs ``task`` at all times.
    If one process dies, another process will run the ``task``.

    Creates a background task that periodically tries to start the user ``task``.
    Before the ``task`` is scheduled for periodic background execution, it acquires a lock.
    Subsequent calls to ``start_exclusive_periodic_task`` will not allow the same ``task``
    to start since the lock will prevent the scheduling.

    Q&A:
    - Why is `_exclusive_task_starter` run as a task?
        This is usually used at setup time and cannot block the setup process forever
    - Why is `_exclusive_task_starter` task a periodic task?
        If Redis connectivity is lost, the periodic `_exclusive_task_starter` ensures the lock is
        reacquired
    """

    @periodic(interval=retry_after)
    @exclusive(
        client,
        lock_key=f"lock:exclusive_task_starter:{task_name}",
        lock_value=f"locked since {arrow.utcnow().format()}",
    )
    @periodic(interval=task_period)
    async def _() -> None:
        await task(**kwargs)

    assert asyncio.iscoroutinefunction(_)  # nosec
    return asyncio.create_task(_())
