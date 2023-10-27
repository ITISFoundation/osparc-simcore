from asyncio import Task
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from fastapi import FastAPI
from pydantic import NonNegativeFloat
from servicelib.background_task import start_periodic_task, stop_periodic_task

from ._store import update_status_cache

_WAIT_FOR_TASK_TO_STOP: Final[NonNegativeFloat] = 5

SERVICES_STATUS_POLL_INTERVAL: Final[timedelta] = timedelta(seconds=60)


@dataclass
class StatusesMonitor:
    app: FastAPI
    task: Task | None = None

    async def _task(self) -> None:
        """run at periodic intervals"""
        # recover the information about all the running services in the system!
        # director-v0 legacy service are only polled
        # director-v2 new style services are both polled and can push updates

        # TODO: fetch all service statuses here and then propagate downstream
        _ = update_status_cache

    async def startup(self) -> None:
        self.task = start_periodic_task(
            self._task,
            interval=SERVICES_STATUS_POLL_INTERVAL,
            task_name="statuses_monitor",
        )

    async def shutdown(self) -> None:
        if self.task:
            await stop_periodic_task(self.task, timeout=_WAIT_FOR_TASK_TO_STOP)


def setup_monitor(app: FastAPI):
    async def on_startup() -> None:
        app.state.statuses_monitor = statuses_monitor = StatusesMonitor(app=app)
        await statuses_monitor.startup()

    async def on_shutdown() -> None:
        statuses_store: StatusesMonitor = app.state.statuses_monitor
        await statuses_store.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
