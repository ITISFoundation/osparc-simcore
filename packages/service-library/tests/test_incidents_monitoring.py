# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import time

import pytest

from servicelib.aiopg_utils import (
    DatabaseError,
    postgres_service_retry_policy_kwargs,
    retry,
)
from servicelib import monitor_slow_callbacks


async def slow_task(delay):
    time.sleep(delay)


@retry(**postgres_service_retry_policy_kwargs)
async def fails_to_reach_pg_db():
    raise DatabaseError


@pytest.fixture
def incidents_manager(loop):
    incidents = []
    monitor_slow_callbacks.enable(slow_duration_secs=0.2, incidents=incidents)

    f1a = asyncio.ensure_future(slow_task(0.3), loop=loop)
    f1b = asyncio.ensure_future(slow_task(0.3), loop=loop)
    f1c = asyncio.ensure_future(slow_task(0.4), loop=loop)

    incidents_pg = None  # aiopg_utils.monitor_pg_responsiveness.enable()
    f2 = asyncio.ensure_future(fails_to_reach_pg_db(), loop=loop)

    yield {"slow_callback": incidents, "posgres_responsive": incidents_pg}


async def test_slow_task_incident(incidents_manager):
    await asyncio.sleep(2)
    assert len(incidents_manager["slow_callback"]) == 3

    delays = [record.delay_secs for record in incidents_manager["slow_callback"]]
    assert max(delays) < 0.5


@pytest.mark.skip(reason="TODO: Design under development")
def test_non_responsive_incident(incidents_manager):
    pass
