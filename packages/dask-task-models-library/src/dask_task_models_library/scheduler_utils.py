from collections.abc import Callable
from typing import Any, Final

import distributed
from aiocache import cached  # type: ignore[import-untyped]
from distributed.objects import SchedulerInfo

_SCHEDULER_IDENTITY_CACHE_TTL_S: Final[int] = 2


def _scheduler_identity_key_builder(func: Callable[..., Any], client: distributed.Client) -> str:
    assert client.scheduler  # nosec
    return f"{func.__module__}.{func.__qualname__}|{client.scheduler.address}"


@cached(ttl=_SCHEDULER_IDENTITY_CACHE_TTL_S, key_builder=_scheduler_identity_key_builder)
async def get_scheduler_details(client: distributed.Client) -> SchedulerInfo:
    """Returns all workers from the scheduler with a short TTL cache.

    We use a live RPC instead of client.scheduler_info(): for asynchronous clients, that local
    cache's "workers" is permanently empty. Both the periodic background refresh and the initial
    connect handshake call Client._update_scheduler_info() with no arguments (n_workers=0), and
    Scheduler.identity(n_workers=0) does itertools.islice(self.workers.values(), 0) -> {} - this
    is by design, not a race (see distributed#9308's discussion), and does NOT converge with time
    or retries. client.scheduler.identity(n_workers=-1) has no such limitation; we cache it
    briefly to avoid redundant round-trips within a single call batch/tick.
    """
    assert client.scheduler  # nosec
    info = await client.scheduler.identity(n_workers=-1)
    assert isinstance(info, dict)  # nosec
    return SchedulerInfo(info)
