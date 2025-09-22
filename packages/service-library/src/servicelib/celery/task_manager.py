from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from models_library.progress_bar import ProgressReport

from ..celery.models import (
    Task,
    TaskEvent,
    TaskFilter,
    TaskID,
    TaskMetadata,
    TaskStatus,
    TaskUUID,
)


@runtime_checkable
class TaskManager(Protocol):
    async def submit_task(
        self, task_metadata: TaskMetadata, *, task_filter: TaskFilter, **task_param
    ) -> TaskUUID: ...

    async def cancel_task(
        self, task_filter: TaskFilter, task_uuid: TaskUUID
    ) -> None: ...

    async def get_task_result(
        self, task_filter: TaskFilter, task_uuid: TaskUUID
    ) -> Any: ...

    async def get_task_status(
        self, task_filter: TaskFilter, task_uuid: TaskUUID
    ) -> TaskStatus: ...

    async def list_tasks(self, task_filter: TaskFilter) -> list[Task]: ...

    async def set_task_progress(
        self, task_id: TaskID, report: ProgressReport
    ) -> None: ...

    async def task_exists(self, task_id: TaskID) -> bool: ...

    # Events

    async def publish_task_event(
        self,
        task_id: TaskID,
        event: TaskEvent,
    ) -> None: ...

    def consume_task_events(
        self,
        task_filter: TaskFilter,
        task_uuid: TaskUUID,
        last_id: str | None = None,
    ) -> AsyncIterator[TaskEvent]: ...
