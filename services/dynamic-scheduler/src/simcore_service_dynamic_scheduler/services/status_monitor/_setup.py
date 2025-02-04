from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Final

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from ._monitor import Monitor

_STATUS_WORKER_DEFAULT_INTERVAL: Final[timedelta] = timedelta(seconds=1)


async def lifespan_status_monitor(app: FastAPI) -> AsyncIterator[State]:
    app.state.status_monitor = monitor = Monitor(
        app, status_worker_interval=_STATUS_WORKER_DEFAULT_INTERVAL
    )
    await monitor.setup()

    yield {}

    await monitor.shutdown()


def get_monitor(app: FastAPI) -> Monitor:
    monitor: Monitor = app.state.status_monitor
    return monitor
