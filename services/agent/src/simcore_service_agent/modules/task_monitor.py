import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from time import time
from typing import Any, Callable, Final, Optional

from fastapi import FastAPI
from pydantic import PositiveFloat, PositiveInt
from servicelib.logging_utils import log_context

from ..core.errors import AgentRuntimeError
from ..core.settings import ApplicationSettings
from .volumes_cleanup import backup_and_remove_volumes

logger = logging.getLogger(__name__)

DEFAULT_TASK_WAIT_ON_ERROR: Final[PositiveInt] = 10


class JobAlreadyRegisteredError(AgentRuntimeError):
    code: str = "agent.task_monitor.job_already_registered"
    msg_template: str = "Job is already registered: {job_name}"


@dataclass
class _TaskData:
    target: Callable
    args: Any
    repeat_interval_s: Optional[PositiveFloat]
    _start_time: Optional[PositiveFloat] = None

    @property
    def job_name(self) -> str:
        return self.target.__name__

    async def run(self) -> None:
        coroutine = self.target(*self.args)

        self._start_time = time()

        try:
            await coroutine
        finally:
            self._start_time = None

    def is_hanging(self) -> bool:
        # NOTE: tasks with no repeat_interval_s are design to run forever
        if self.repeat_interval_s is None:
            return False

        if self._start_time is None:
            return False

        return (time() - self._start_time) > self.repeat_interval_s


async def _task_runner(task_data: _TaskData) -> None:
    with log_context(logger, logging.INFO, msg=f"'{task_data.job_name}'"):
        while True:
            try:
                await task_data.run()
            except Exception:  # pylint: disable=broad-except
                logger.exception("Had an error while running '%s'", task_data.job_name)

            if task_data.repeat_interval_s is None:
                logger.warning(
                    "Unexpected termination of '%s'; it will be restarted",
                    task_data.job_name,
                )

            logger.info(
                "Will run '%s' again in %s seconds",
                task_data.job_name,
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
    _tasks: dict[str, asyncio.Task] = field(default_factory=dict)
    _to_start: dict[str, _TaskData] = field(default_factory=dict)

    @property
    def was_started(self) -> bool:
        return self._was_started

    @property
    def are_tasks_hanging(self) -> bool:
        hanging_tasks_detected = False
        for name, task_data in self._to_start.items():
            if task_data.is_hanging():
                logger.warning("Task '%s' is hanging", name)
                hanging_tasks_detected = True
        return hanging_tasks_detected

    def register_job(
        self,
        target: Callable,
        *args: Any,
        repeat_interval_s: Optional[PositiveFloat] = None,
    ) -> None:
        task_data = _TaskData(target, args, repeat_interval_s)
        job_name = task_data.job_name
        if job_name in self._to_start:
            raise JobAlreadyRegisteredError(job_name=job_name)

        self._to_start[job_name] = task_data

    def start_job(self, name: str) -> None:
        task_data: _TaskData = self._to_start[name]
        self._tasks[task_data.job_name] = asyncio.create_task(
            _task_runner(task_data), name=f"task_{name}"
        )

    async def unregister_job(self, target: Callable) -> None:
        job_name = target.__name__
        task: Optional[asyncio.Task] = self._tasks.get(job_name, None)
        if task is not None:
            await self._cancel_task(task)
            del self._tasks[job_name]
        del self._to_start[job_name]

    async def start(self) -> None:
        """schedule tasks for all jobs"""
        for name in self._to_start:
            logger.info("Starting task '%s'", name)
            self.start_job(name)
        self._was_started = True

    @staticmethod
    async def _cancel_task(task: asyncio.Task) -> None:
        async def _wait_for_task(task: asyncio.Task) -> None:
            with suppress(asyncio.CancelledError):
                await task

        logger.info("Cancel task '%s'", task.get_name())
        task.cancel()
        await _wait_for_task(task)

    async def shutdown(self):
        await asyncio.gather(
            *(self._cancel_task(t) for t in self._tasks.values()),
            return_exceptions=True,
        )

        self._was_started = False
        self._tasks.clear()
        self._to_start.clear()


async def disable_volume_removal_task(app: FastAPI) -> None:
    task_monitor: TaskMonitor = app.state.task_monitor

    await task_monitor.unregister_job(backup_and_remove_volumes)


async def enable_volume_removal_task_if_missing(app: FastAPI) -> None:
    task_monitor: TaskMonitor = app.state.task_monitor
    settings: ApplicationSettings = app.state.settings

    try:
        task_monitor.register_job(
            backup_and_remove_volumes,
            app,
            repeat_interval_s=settings.AGENT_VOLUMES_CLEANUP_INTERVAL_S,
        )
        task_monitor.start_job(backup_and_remove_volumes.__name__)
    except JobAlreadyRegisteredError:
        logger.debug(
            "Job '%s' was already registered.",
            backup_and_remove_volumes.__name__,
        )


def setup(app: FastAPI) -> None:
    async def _on_startup() -> None:
        task_monitor = app.state.task_monitor = TaskMonitor()

        await task_monitor.start()
        # setup all relative jobs
        await enable_volume_removal_task_if_missing(app)

        logger.info("Started 🔍 task_monitor")

    async def _on_shutdown() -> None:
        task_monitor: TaskMonitor = app.state.task_monitor
        await task_monitor.shutdown()
        logger.info("Stopped 🔍 task_monitor")

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


__all__: tuple[str, ...] = (
    "disable_volume_removal_task",
    "setup",
    "TaskMonitor",
)
