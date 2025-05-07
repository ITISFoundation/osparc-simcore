from asyncio import Task, create_task, wait_for
from contextlib import suppress
from datetime import timedelta
from typing import Any, Final

from pydantic import NonNegativeFloat

from ....async_utils import cancel_wait_task
from ..._models import JobUniqueId, RemoteHandlerName, StartParams
from ...runners.base import BaseServerJobInterface
from ._errors import HandlerNotRegisteredError, TaskNotFoundError
from ._registry import AsyncTaskRegistry

_MAX_CANCEL_DURATION_S: Final[NonNegativeFloat] = 1


class AsyncioTasksJobInterface(BaseServerJobInterface):
    def __init__(self, registry: AsyncTaskRegistry) -> None:
        self.registry = registry
        self._tasks: dict[JobUniqueId, Task] = {}

    async def shutdown(self) -> None:
        for task in self._tasks:
            await self.remove(task)

    async def start(
        self,
        name: RemoteHandlerName,
        unique_id: JobUniqueId,
        params: StartParams,
        timeout: timedelta,  # noqa: ASYNC109
    ) -> None:
        """used to start a job"""
        if name not in self.registry.handlers:
            raise HandlerNotRegisteredError(name=name)

        handler = self.registry.handlers[name]
        self._tasks[unique_id] = create_task(
            wait_for(handler(**params), timeout.total_seconds()), name=unique_id
        )

    async def remove(self, unique_id: JobUniqueId) -> None:
        if unique_id not in self._tasks:
            return

        # errors are raised if taks was already finished
        with suppress(Exception):
            await cancel_wait_task(
                self._tasks[unique_id], max_delay=_MAX_CANCEL_DURATION_S
            )

        del self._tasks[unique_id]

    async def is_present(self, unique_id: JobUniqueId) -> bool:
        """returns True if the job exists"""
        return unique_id in self._tasks

    async def is_running(self, unique_id: JobUniqueId) -> bool:
        """returns True if the job is currently running"""
        if unique_id not in self._tasks:
            return False

        task = self._tasks[unique_id]
        return not task.done()

    async def get_result(self, unique_id: JobUniqueId) -> Any | None:
        """provides the result of the job once finished"""
        if unique_id not in self._tasks:
            raise TaskNotFoundError(unique_id=unique_id)

        task = self._tasks[unique_id]
        return task.result()


# TODO: add tests individually for these so we knoe they work when registring starting and stopping and all the operations. Also cancellation
