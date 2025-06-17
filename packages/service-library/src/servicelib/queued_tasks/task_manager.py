from typing import Any, Protocol

from ..queued_tasks.models import (
    ProgressReport,
    Task,
    TaskContext,
    TaskID,
    TaskMetadata,
    TaskStatus,
    TaskUUID,
)


class TaskManager(Protocol):
    async def submit_task(
        self, task_metadata: TaskMetadata, *, task_context: TaskContext, **task_param
    ) -> TaskUUID: ...

    async def cancel_task(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> None: ...

    async def get_task_result(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> Any: ...

    async def get_task_status(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> TaskStatus: ...

    async def list_tasks(self, task_context: TaskContext) -> list[Task]: ...

    async def set_task_progress(
        self, task_id: TaskID, report: ProgressReport
    ) -> None: ...
