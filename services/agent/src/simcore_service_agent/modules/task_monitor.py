import asyncio
import logging
from collections import deque
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Coroutine, Final, Optional

from fastapi import FastAPI
from pydantic import PositiveFloat, PositiveInt
from servicelib.logging_utils import log_context

from ..core.settings import ApplicationSettings
from .volumes_cleanup import backup_and_remove_volumes

logger = logging.getLogger(__name__)

DEFAULT_TASK_WAIT_ON_ERROR: Final[PositiveInt] = 10


@dataclass
class _TaskData:
    target: Callable
    args: Any
    repeat_interval_s: Optional[PositiveFloat]

    @property
    def name(self) -> str:
        return self.target.__name__

    def get_coroutine(self) -> Coroutine:
        coroutine = self.target(*self.args)
        assert isinstance(coroutine, Coroutine)  # nosec
        return coroutine


async def _task_runner(task_data: _TaskData) -> None:
    with log_context(logger, logging.INFO, msg=f"'{task_data.name}'"):
        while True:
            try:
                await task_data.get_coroutine()
            except Exception:  # pylint: disable=broad-except
                logger.exception("Had an error while running '%s'", task_data.name)

            if task_data.repeat_interval_s is None:
                logger.warning(
                    "Unexpected termination of '%s'; it will be restarted",
                    task_data.name,
                )

            logger.info(
                "Will run '%s' again in %s seconds",
                task_data.name,
                task_data.repeat_interval_s,
            )
            await asyncio.sleep(
                DEFAULT_TASK_WAIT_ON_ERROR
                if task_data.repeat_interval_s is None
                else task_data.repeat_interval_s
            )


@dataclass
class TaskMonitor:
    _was_started: bool = False
    _tasks: set[asyncio.Task] = field(default_factory=set)
    _to_start: dict[str, _TaskData] = field(default_factory=dict)

    @property
    def was_started(self) -> bool:
        return self._was_started

    def register_job(
        self,
        target: Callable,
        *args: Any,
        repeat_interval_s: Optional[PositiveFloat] = None,
    ) -> None:
        if self._was_started:
            raise RuntimeError(
                "Cannot add more tasks, monitor already running with: "
                f"{[x.get_name() for x in self._tasks]}"
            )

        task_data = _TaskData(target, args, repeat_interval_s)
        if task_data.name in self._to_start:
            raise RuntimeError(f"{target.__name__} is already registered")

        self._to_start[target.__name__] = task_data

    async def start(self) -> None:
        self._was_started = True
        for name, task_data in self._to_start.items():
            logger.info("Starting task '%s'", name)
            self._tasks.add(
                asyncio.create_task(_task_runner(task_data), name=f"task_{name}")
            )

    async def shutdown(self):
        async def _wait_for_task(task: asyncio.Task) -> None:
            with suppress(asyncio.CancelledError):
                await task

        tasks_to_wait: deque[Awaitable] = deque()
        for task in set(self._tasks):
            logger.info("Cancel and stop task '%s'", task.get_name())

            task.cancel()
            tasks_to_wait.append(_wait_for_task(task))
            self._tasks.remove(task)

        await asyncio.gather(*tasks_to_wait, return_exceptions=True)
        self._was_started = False
        self._to_start = {}


def setup(app: FastAPI) -> None:
    async def _on_startup() -> None:
        task_monitor = app.state.task_monitor = TaskMonitor()
        settings: ApplicationSettings = app.state.settings

        # setup all relative jobs
        task_monitor.register_job(
            backup_and_remove_volumes,
            settings,
            repeat_interval_s=settings.AGENT_VOLUMES_CLEANUP_INTERVAL_S,
        )

        await task_monitor.start()
        logger.info("Started 🔍 task_monitor")

    async def _on_shutdown() -> None:
        task_monitor: TaskMonitor = app.state.task_monitor
        await task_monitor.shutdown()
        logger.info("Stopped 🔍 task_monitor")

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


__all__: tuple[str, ...] = (
    "setup",
    "TaskMonitor",
)
