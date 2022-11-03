import asyncio
import logging
import traceback
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Coroutine, Final, Optional

from fastapi import FastAPI
from pydantic import PositiveFloat, PositiveInt

from ..core.settings import ApplicationSettings
from .volumes_cleanup import backup_and_remove_volumes

logger = logging.getLogger(__name__)

DEFAULT_TASK_WAIT_ON_ERROR: Final[PositiveInt] = 10


@dataclass
class _TaskData:
    callable: Callable
    args: Any
    repeat_interval_s: Optional[PositiveFloat]


async def _task_runner(task_data: _TaskData) -> None:
    while True:
        coroutine: Coroutine = task_data.callable(*task_data.args)
        logger.info("Running '%s'", coroutine.__name__)
        try:
            await coroutine
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Had an error while running '%s':\n%s",
                coroutine.__name__,
                "\n".join(traceback.format_tb(e.__traceback__)),
            )

        if task_data.repeat_interval_s is None:
            logger.warning(
                "Unexpected termination of '%s'; it will be restarted",
                coroutine.__name__,
            )

        logger.info(
            "Will run '%s' again in %s seconds",
            coroutine.__name__,
            task_data.repeat_interval_s,
        )
        await asyncio.sleep(
            DEFAULT_TASK_WAIT_ON_ERROR
            if task_data.repeat_interval_s is None
            else task_data.repeat_interval_s
        )


class TaskMonitor:
    def __init__(self):
        self._started: bool = False
        self._tasks: set[asyncio.Task] = set()

        self._to_start: dict[str, _TaskData] = {}

    def list_running(self) -> str:
        return "\n- ".join(["Running tasks:"] + list(self._to_start.keys()))

    def register_job(
        self,
        target: Callable,
        *args: Any,
        repeat_interval_s: Optional[PositiveFloat] = None,
    ) -> None:
        if self._started:
            raise RecursionError(
                "Cannot add more tasks, monitor already running with: "
                f"{[x.get_name() for x in self._tasks]}"
            )

        if target.__name__ in self._to_start:
            raise RuntimeError(f"{target.__name__} is already registered")

        self._to_start[target.__name__] = _TaskData(target, args, repeat_interval_s)

    async def start(self) -> None:
        self._started = True
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
        for task in self._tasks:
            logger.info("Cancel and stop task '%s'", task.get_name())

            task.cancel()
            tasks_to_wait.append(_wait_for_task(task))

        await asyncio.gather(*tasks_to_wait)
        self._started = False


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

    async def _on_shutdown() -> None:
        task_monitor: TaskMonitor = app.state.task_monitor
        await task_monitor.shutdown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


__all__: tuple[str, ...] = (
    "setup",
    "TaskMonitor",
)
