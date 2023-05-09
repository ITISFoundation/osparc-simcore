import asyncio
import contextlib
import logging
from asyncio import Lock, Queue, Task
from dataclasses import dataclass, field

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from .....models.schemas.dynamic_services import SchedulerData, ServiceName
from .._abc import SchedulerInternalsInterface

logger = logging.getLogger(__name__)


@dataclass
class SchedulerInternalsMixin(  # pylint: disable=too-many-instance-attributes
    SchedulerInternalsInterface
):
    app: FastAPI

    _lock: Lock = field(default_factory=Lock)
    _to_observe: dict[ServiceName, SchedulerData] = field(default_factory=dict)
    _service_observation_task: dict[ServiceName, asyncio.Task | object | None] = field(
        default_factory=dict
    )
    _keep_running: bool = False
    _inverse_search_mapping: dict[NodeID, ServiceName] = field(default_factory=dict)
    _scheduler_task: Task | None = None
    _cleanup_volume_removal_services_task: Task | None = None
    _trigger_observation_queue_task: Task | None = None
    _trigger_observation_queue: Queue = field(default_factory=Queue)
    _observation_counter: int = 0

    async def start(self) -> None:
        # run as a background task
        logger.info("Starting dynamic-sidecar scheduler")
        self._keep_running = True
        self._scheduler_task = asyncio.create_task(
            self._run_scheduler_task(), name="dynamic-scheduler"
        )
        self._trigger_observation_queue_task = asyncio.create_task(
            self._run_trigger_observation_queue_task(),
            name="dynamic-scheduler-trigger-obs-queue",
        )

        self._cleanup_volume_removal_services_task = asyncio.create_task(
            self._cleanup_volume_removal_services(),
            name="dynamic-scheduler-cleanup-volume-removal-services",
        )
        await self._discover_running_services()

    async def shutdown(self) -> None:
        logger.info("Shutting down dynamic-sidecar scheduler")
        self._keep_running = False
        self._inverse_search_mapping = {}
        self._to_observe = {}

        if self._cleanup_volume_removal_services_task is not None:
            self._cleanup_volume_removal_services_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_volume_removal_services_task
            self._cleanup_volume_removal_services_task = None

        if self._scheduler_task is not None:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task
            self._scheduler_task = None

        if self._trigger_observation_queue_task is not None:
            await self._trigger_observation_queue.put(None)

            self._trigger_observation_queue_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._trigger_observation_queue_task
            self._trigger_observation_queue_task = None
            self._trigger_observation_queue = Queue()

        # let's properly cleanup remaining observation tasks
        running_tasks = [
            x for x in self._service_observation_task.values() if isinstance(x, Task)
        ]
        for task in running_tasks:
            task.cancel()
        try:
            MAX_WAIT_TIME_SECONDS = 5
            results = await asyncio.wait_for(
                asyncio.gather(*running_tasks, return_exceptions=True),
                timeout=MAX_WAIT_TIME_SECONDS,
            )
            if bad_results := list(filter(lambda r: isinstance(r, Exception), results)):
                logger.error(
                    "Following observation tasks completed with an unexpected error:%s",
                    f"{bad_results}",
                )
        except asyncio.TimeoutError:
            logger.error(
                "Timed-out waiting for %s to complete. Action: Check why this is blocking",
                f"{running_tasks=}",
            )
