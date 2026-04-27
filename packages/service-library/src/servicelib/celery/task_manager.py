from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from models_library.celery import (
    GroupExecutionMetadata,
    Task,
    TaskExecutionMetadata,
    TaskID,
    TaskStatus,
    TaskStreamItem,
)
from models_library.progress_bar import ProgressReport


@runtime_checkable
class TaskManager(Protocol):
    async def submit_group(
        self,
        execution_metadata: GroupExecutionMetadata,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> tuple[TaskID, list[TaskID]]: ...

    async def submit_task(
        self,
        execution_metadata: TaskExecutionMetadata,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
        **task_params,
    ) -> TaskID: ...

    async def cancel(self, task_id: TaskID) -> None: ...

    async def get_result(self, task_id: TaskID) -> Any: ...

    async def get_status(self, task_id: TaskID) -> TaskStatus: ...

    async def list_tasks(
        self,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> list[Task]: ...

    async def set_task_progress(self, task_id: TaskID, report: ProgressReport) -> None: ...

    async def push_task_stream_items(self, task_id: TaskID, *items: TaskStreamItem) -> None: ...

    async def pull_task_stream_items(
        self,
        task_id: TaskID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[TaskStreamItem], bool, datetime | None]: ...

    async def set_task_stream_done(self, task_id: TaskID) -> None: ...

    async def set_task_stream_last_update(self, task_id: TaskID) -> None: ...

    async def task_exists(self, task_id: TaskID) -> bool: ...
