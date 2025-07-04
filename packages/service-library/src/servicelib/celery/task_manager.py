from typing import Any, Protocol

from models_library.progress_bar import ProgressReport

from ..celery.models import (
    TASK_QUEUE_DEFAULT,
    Task,
    TaskContext,
    TaskID,
    TaskName,
    TaskQueue,
    TaskStatus,
    TaskUUID,
)


class TaskManager(Protocol):
    async def send_task(
        self,
        name: TaskName,
        context: TaskContext,
        *,
        ephemeral: bool = True,
        queue: TaskQueue = TASK_QUEUE_DEFAULT,
        **params,
    ) -> TaskUUID: ...

    async def cancel_task(self, context: TaskContext, task_uuid: TaskUUID) -> None: ...

    async def get_task_result(
        self, context: TaskContext, task_uuid: TaskUUID
    ) -> Any: ...

    async def get_task_status(
        self, context: TaskContext, task_uuid: TaskUUID
    ) -> TaskStatus: ...

    async def list_tasks(self, context: TaskContext) -> list[Task]: ...

    async def set_task_progress(
        self, task_id: TaskID, report: ProgressReport
    ) -> None: ...
