import asyncio
import datetime
import logging
from collections.abc import Awaitable, Callable

import arrow

from ..background_task import periodic
from ._client import RedisClientSDK
from ._decorators import exclusive

_logger = logging.getLogger(__name__)


def create_exclusive_periodic_task(
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
    If the process dies, and another replica exists, it will take over the ``task``.

    Creates a background task that periodically tries to acquire a distributed lock
    and then runs another background task that periodically runs the user ``task``.
    Only the process that acquired the lock will run the user ``task``.

    Q&A:
    - Why is `_exclusive_task_starter` task a periodic task?
        If Redis connectivity is lost, the periodic acquisition of the lock shall kick in
    """

    @periodic(interval=retry_after)
    @exclusive(
        client,
        lock_key=f"lock:exclusive_periodic_task:{task_name}",
        lock_value=f"locked since {arrow.utcnow().format()} by {client.client_name}",
    )
    @periodic(interval=task_period)
    async def _() -> None:
        await task(**kwargs)

    assert asyncio.iscoroutinefunction(_)  # nosec
    return asyncio.create_task(_())
