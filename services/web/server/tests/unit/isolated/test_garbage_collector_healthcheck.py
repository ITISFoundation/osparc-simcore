# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# ruff: noqa: SLF001

import asyncio
import datetime

import pytest
from aiohttp import web
from simcore_service_webserver.garbage_collector import _healthcheck, _tasks_utils
from simcore_service_webserver.garbage_collector.settings import GarbageCollectorSettings
from simcore_service_webserver.rest.healthcheck import HealthCheckError


@pytest.fixture
def app() -> web.Application:
    return web.Application()


@pytest.fixture
def settings() -> GarbageCollectorSettings:
    return GarbageCollectorSettings(
        GARBAGE_COLLECTOR_TASK_STALE_FACTOR=2.0,
        GARBAGE_COLLECTOR_TASK_MIN_STALENESS=datetime.timedelta(seconds=1),
    )


def _set_registered_task(app: web.Application, task_name: str, task: asyncio.Task) -> None:
    app.setdefault(_tasks_utils._GC_PERIODIC_TASKS_APPKEY, {})
    app[_tasks_utils._GC_PERIODIC_TASKS_APPKEY][task_name] = task


async def test_healthy_when_task_running_and_heartbeat_fresh(app: web.Application, settings: GarbageCollectorSettings):
    task_name = "task-healthy"
    _healthcheck.register_task_liveness(app, task_name, interval=datetime.timedelta(seconds=1), settings=settings)

    running_task = asyncio.create_task(asyncio.sleep(10))
    _set_registered_task(app, task_name, running_task)
    _healthcheck.mark_task_heartbeat(app, task_name)

    await _healthcheck.on_healthcheck_async_adapter(app)  # does not raise

    running_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running_task


async def test_unhealthy_when_task_was_never_started(app: web.Application, settings: GarbageCollectorSettings):
    task_name = "task-never-started"
    _healthcheck.register_task_liveness(app, task_name, interval=datetime.timedelta(seconds=1), settings=settings)

    with pytest.raises(HealthCheckError, match="was never started"):
        await _healthcheck.on_healthcheck_async_adapter(app)


async def test_unhealthy_when_task_stopped_with_exception(app: web.Application, settings: GarbageCollectorSettings):
    task_name = "task-crashed"
    _healthcheck.register_task_liveness(app, task_name, interval=datetime.timedelta(seconds=1), settings=settings)

    async def _boom() -> None:
        msg = "boom"
        raise RuntimeError(msg)

    failed_task = asyncio.create_task(_boom())
    with pytest.raises(RuntimeError, match="boom"):
        await failed_task

    _set_registered_task(app, task_name, failed_task)

    with pytest.raises(HealthCheckError, match="stopped running"):
        await _healthcheck.on_healthcheck_async_adapter(app)


async def test_unhealthy_when_task_was_cancelled(app: web.Application, settings: GarbageCollectorSettings):
    task_name = "task-cancelled"
    _healthcheck.register_task_liveness(app, task_name, interval=datetime.timedelta(seconds=1), settings=settings)

    cancelled_task = asyncio.create_task(asyncio.sleep(10))
    cancelled_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_task

    _set_registered_task(app, task_name, cancelled_task)

    with pytest.raises(HealthCheckError, match="cancelled"):
        await _healthcheck.on_healthcheck_async_adapter(app)


async def test_unhealthy_when_heartbeat_is_stale(app: web.Application, settings: GarbageCollectorSettings):
    task_name = "task-hanging"
    interval = datetime.timedelta(seconds=1)
    _healthcheck.register_task_liveness(app, task_name, interval=interval, settings=settings)

    running_task = asyncio.create_task(asyncio.sleep(10))
    _set_registered_task(app, task_name, running_task)

    # force the last heartbeat far enough in the past to exceed max_staleness (interval * factor)
    liveness = app[_healthcheck._GC_TASKS_LIVENESS_APPKEY][task_name]
    liveness.last_heartbeat_utc -= datetime.timedelta(seconds=1000)

    with pytest.raises(HealthCheckError, match="might be hanging"):
        await _healthcheck.on_healthcheck_async_adapter(app)

    running_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running_task


async def test_healthy_when_no_tasks_registered(app: web.Application):
    await _healthcheck.on_healthcheck_async_adapter(app)  # does not raise


async def test_min_staleness_protects_fast_tasks_from_false_positives(app: web.Application):
    # a fast task (1s interval) with a low factor would normally allow only 1s of staleness,
    # but GARBAGE_COLLECTOR_TASK_MIN_STALENESS enforces a higher floor
    settings = GarbageCollectorSettings(
        GARBAGE_COLLECTOR_TASK_STALE_FACTOR=1.0,
        GARBAGE_COLLECTOR_TASK_MIN_STALENESS=datetime.timedelta(hours=1),
    )
    task_name = "task-fast"
    _healthcheck.register_task_liveness(app, task_name, interval=datetime.timedelta(seconds=1), settings=settings)

    running_task = asyncio.create_task(asyncio.sleep(10))
    _set_registered_task(app, task_name, running_task)

    # 10s of staleness exceeds interval * factor (1s) but is well within the 1h floor
    liveness = app[_healthcheck._GC_TASKS_LIVENESS_APPKEY][task_name]
    liveness.last_heartbeat_utc -= datetime.timedelta(seconds=10)

    await _healthcheck.on_healthcheck_async_adapter(app)  # does not raise

    running_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running_task
