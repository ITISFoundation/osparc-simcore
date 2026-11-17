"""helpers for tests that need to observe PostgreSQL row-level lock contention"""

from collections.abc import Awaitable, Callable
from typing import Final

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from tenacity import retry, retry_if_result, stop_after_delay, wait_fixed

TIMEOUT_S: Final[float] = 30.0
DEADLOCK_SQLSTATE: Final[str] = "40P01"
_LOCK_WAITERS_SQL: Final[str] = (
    "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
)
_WAITERS_BEHIND_SQL: Final[str] = (
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE wait_event_type = 'Lock' AND pid <> pg_backend_pid() AND :pid = ANY(pg_blocking_pids(pid))"
)


def sqlstate(exc: BaseException) -> str | None:
    """the PostgreSQL SQLSTATE of a driver exception, e.g. DEADLOCK_SQLSTATE"""
    return getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(exc, "sqlstate", None)


async def get_backend_pid(connection: AsyncConnection) -> int:
    """the pid that waiting sessions report as the lock holder when blocked on this connection"""
    return int(await connection.scalar(sa.text("SELECT pg_backend_pid()")))


async def count_lock_waiters(engine: AsyncEngine) -> int:
    """sessions (other than the probe itself) waiting on any lock"""
    async with engine.connect() as probe:
        return int(await probe.scalar(sa.text(_LOCK_WAITERS_SQL)))


async def count_lock_waiters_behind(engine: AsyncEngine, holder_pid: int) -> int:
    """sessions (other than the probe itself) waiting on a lock held by `holder_pid`"""
    async with engine.connect() as probe:
        return int(await probe.scalar(sa.text(_WAITERS_BEHIND_SQL), {"pid": holder_pid}))


async def wait_until(condition: Callable[[], Awaitable[bool]], what: str, *, timeout_s: float = TIMEOUT_S) -> None:
    """polls `condition` until it holds — use when there is no event to wait for, e.g.
    polling the lock state of the database — or fails the test with `what` after `timeout_s`
    """

    @retry(
        retry=retry_if_result(lambda done: not done),
        stop=stop_after_delay(timeout_s),
        wait=wait_fixed(0.05),
        retry_error_callback=lambda _: pytest.fail(what),
    )
    async def _poll() -> bool:
        return await condition()

    await _poll()
