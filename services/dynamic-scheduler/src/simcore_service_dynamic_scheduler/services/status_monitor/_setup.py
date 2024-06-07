from datetime import timedelta
from typing import Final

from fastapi import FastAPI

from ._monitor import Monitor

_STATUS_WORKER_DEFAULT_INTERVAL: Final[timedelta] = timedelta(seconds=1)


def setup_status_monitor(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.status_monitor = monitor = Monitor(
            app, status_worker_interval=_STATUS_WORKER_DEFAULT_INTERVAL
        )
        await monitor.setup()

    async def on_shutdown() -> None:
        monitor: Monitor = app.state.status_monitor
        await monitor.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_monitor(app: FastAPI) -> Monitor:
    monitor: Monitor = app.state.status_monitor
    return monitor
