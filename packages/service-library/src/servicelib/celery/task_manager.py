from typing import Any, Protocol, runtime_checkable

from models_library.progress_bar import ProgressReport

from ..celery.models import (
    Task,
    TaskExecutionMetadata,
    TaskID,
    TaskOwnerMetadata,
    TaskStatus,
    TaskUUID,
)


@runtime_checkable
class TaskManager(Protocol):
    async def submit_task(
        self,
        task_metadata: TaskExecutionMetadata,
        *,
        task_filter: TaskOwnerMetadata,
        **task_param
    ) -> TaskUUID: ...

    async def cancel_task(
        self, task_filter: TaskOwnerMetadata, task_uuid: TaskUUID
    ) -> None: ...

    async def task_exists(self, task_id: TaskID) -> bool: ...

    async def get_task_result(
        self, task_filter: TaskOwnerMetadata, task_uuid: TaskUUID
    ) -> Any: ...

    async def get_task_status(
        self, task_filter: TaskOwnerMetadata, task_uuid: TaskUUID
    ) -> TaskStatus: ...

    async def list_tasks(self, task_filter: TaskOwnerMetadata) -> list[Task]: ...

    async def set_task_progress(
        self, task_id: TaskID, report: ProgressReport
    ) -> None: ...
