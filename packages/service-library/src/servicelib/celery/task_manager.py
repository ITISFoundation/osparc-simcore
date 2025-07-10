from typing import Any, Protocol

from models_library.progress_bar import ProgressReport

from ..celery.models import (
    TASK_QUEUE_DEFAULT,
    Task,
    TaskFilter,
    TaskID,
    TaskName,
    TaskQueue,
    TaskStatus,
    TaskUUID,
)


class TaskManager(Protocol):
    async def send_task(
        self,
        task_name: TaskName,
        task_filter: TaskFilter,
        *,
        task_ephemeral: bool = True,
        task_queue: TaskQueue = TASK_QUEUE_DEFAULT,
        **task_params,
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
