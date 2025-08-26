# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import asyncio
import time
from collections.abc import Iterable

import pytest
import pytest_asyncio
from servicelib.aiohttp import monitor_slow_callbacks
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


async def _slow_function(delay):
    time.sleep(delay)  # noqa: ASYNC251


@retry(wait=wait_fixed(1), stop=stop_after_attempt(2))
async def _raising_function():
    msg = "This function is expected to raise an error"
    raise RuntimeError(msg)


@pytest_asyncio.fixture(loop_scope="function", scope="function")
async def incidents_manager() -> dict:
    incidents = []
    monitor_slow_callbacks.enable(slow_duration_secs=0.2, incidents=incidents)

    event_loop = asyncio.get_running_loop()
    asyncio.ensure_future(_slow_function(0.3), loop=event_loop)  # noqa: RUF006
    asyncio.ensure_future(_slow_function(0.3), loop=event_loop)  # noqa: RUF006
    asyncio.ensure_future(_slow_function(0.4), loop=event_loop)  # noqa: RUF006

    incidents_pg = None  # aiopg_utils.monitor_pg_responsiveness.enable()
    asyncio.ensure_future(_raising_function(), loop=event_loop)  # noqa: RUF006

    return {"slow_callback": incidents, "posgres_responsive": incidents_pg}


@pytest.fixture
def disable_monitoring() -> Iterable[None]:
    original_handler = asyncio.events.Handle._run  # noqa: SLF001
    yield None
    asyncio.events.Handle._run = original_handler  # noqa: SLF001


@pytest.mark.skip(
    reason="log_slow_callbacks is not supported out-of-the-box with uvloop."
    " SEE https://github.com/ITISFoundation/osparc-simcore/issues/8047"
)
async def test_slow_task_incident(disable_monitoring: None, incidents_manager: dict):
    await asyncio.sleep(2)
    assert len(incidents_manager["slow_callback"]) == 3

    delays = [record.delay_secs for record in incidents_manager["slow_callback"]]
    assert max(delays) < 0.5
