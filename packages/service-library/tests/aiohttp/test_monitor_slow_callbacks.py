# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import asyncio
import time
from collections.abc import Iterable

import pytest
from servicelib.aiohttp import monitor_slow_callbacks
from servicelib.aiohttp.aiopg_utils import DatabaseError
from servicelib.aiohttp.incidents import LimitedOrderedStack, SlowCallback
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


async def slow_sync_sleeper_task(delay):
    time.sleep(delay)  # noqa: ASYNC251


@retry(wait=wait_fixed(1), stop=stop_after_attempt(2))
async def fails_to_reach_pg_db():
    raise DatabaseError


@pytest.fixture
async def incidents_manager() -> dict:
    incidents: LimitedOrderedStack[SlowCallback] = LimitedOrderedStack[SlowCallback](
        max_size=10
    )
    monitor_slow_callbacks.enable(slow_duration_secs=0.2, incidents=incidents)

    f1 = asyncio.ensure_future(
        slow_sync_sleeper_task(0.3), loop=asyncio.get_event_loop()
    )
    assert f1
    f2 = asyncio.ensure_future(
        slow_sync_sleeper_task(0.3), loop=asyncio.get_event_loop()
    )
    assert f2
    f3 = asyncio.ensure_future(
        slow_sync_sleeper_task(0.4), loop=asyncio.get_event_loop()
    )
    assert f3

    incidents_pg = None  # aiopg_utils.monitor_pg_responsiveness.enable()
    f4 = asyncio.ensure_future(fails_to_reach_pg_db(), loop=asyncio.get_event_loop())
    assert f4

    return {"slow_callback": incidents, "postgres_responsive": incidents_pg}


@pytest.fixture
def disable_monitoring() -> Iterable[None]:
    original_handler = asyncio.events.Handle._run  # noqa: SLF001
    yield None
    asyncio.events.Handle._run = original_handler  # noqa: SLF001


async def test_slow_task_incident(disable_monitoring: None, incidents_manager: dict):
    await asyncio.sleep(2)
    assert len(incidents_manager["slow_callback"]) == 3

    delays = [record.delay_secs for record in incidents_manager["slow_callback"]]
    assert max(delays) < 0.5
