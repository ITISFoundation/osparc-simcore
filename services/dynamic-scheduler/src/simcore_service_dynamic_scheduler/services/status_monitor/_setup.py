from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Final

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from ._monitor import Monitor

_STATUS_WORKER_DEFAULT_INTERVAL: Final[timedelta] = timedelta(seconds=1)


async def _status_monitor_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.status_monitor = monitor = Monitor(app, status_worker_interval=_STATUS_WORKER_DEFAULT_INTERVAL)
    await monitor.setup()

    yield {}

    await monitor.shutdown()


def configure_status_monitor(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_status_monitor_lifespan)


def get_monitor(app: FastAPI) -> Monitor:
    monitor: Monitor = app.state.status_monitor
    return monitor
