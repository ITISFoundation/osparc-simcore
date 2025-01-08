import asyncio
import datetime
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import arrow
import redis.exceptions
from redis.asyncio.lock import Lock
from servicelib.background_task import start_periodic_task

from ..logging_utils import log_context
from ._client import RedisClientSDK
from ._constants import SHUTDOWN_TIMEOUT_S
from ._decorators import exclusive
from ._errors import CouldNotAcquireLockError, LockLostError

_logger = logging.getLogger(__name__)


async def cancel_or_warn(task: asyncio.Task) -> None:
    if not task.cancelled():
        task.cancel()
    _, pending = await asyncio.wait((task,), timeout=SHUTDOWN_TIMEOUT_S)
    if pending:
        task_name = task.get_name()
        _logger.warning("Could not cancel task_name=%s pending=%s", task_name, pending)


async def auto_extend_lock(lock: Lock) -> None:
    try:
        with log_context(_logger, logging.DEBUG, f"Autoextend lock {lock.name}"):
            await lock.reacquire()
    except redis.exceptions.LockNotOwnedError as exc:
        raise LockLostError(lock=lock) from exc


async def _exclusive_task_starter(
    client: RedisClientSDK,
    usr_tsk_task: Callable[..., Awaitable[None]],
    *,
    usr_tsk_interval: datetime.timedelta,
    usr_tsk_task_name: str,
    **kwargs,
) -> None:
    lock_key = f"lock:exclusive_task_starter:{usr_tsk_task_name}"
    lock_value = f"locked since {arrow.utcnow().format()}"

    try:
        await exclusive(client, lock_key=lock_key, lock_value=lock_value)(
            start_periodic_task
        )(
            usr_tsk_task,
            interval=usr_tsk_interval,
            task_name=usr_tsk_task_name,
            **kwargs,
        )
    except CouldNotAcquireLockError:
        _logger.debug(
            "Could not acquire lock '%s' with value '%s'", lock_key, lock_value
        )
    except Exception as e:
        _logger.exception(e)  # noqa: TRY401
        raise


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
    return start_periodic_task(
        _exclusive_task_starter,
        interval=retry_after,
        task_name=f"exclusive_task_starter_{task_name}",
        client=client,
        usr_tsk_task=task,
        usr_tsk_interval=task_period,
        usr_tsk_task_name=task_name,
        **kwargs,
    )


async def handle_redis_returns_union_types(result: Any | Awaitable[Any]) -> Any:
    """Used to handle mypy issues with redis 5.x return types"""
    if isinstance(result, Awaitable):
        return await result
    return result
