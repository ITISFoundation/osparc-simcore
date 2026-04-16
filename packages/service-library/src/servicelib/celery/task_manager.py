from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from models_library.celery import (
    GroupExecutionMetadata,
    GroupKey,
    GroupStatus,
    GroupUUID,
    Task,
    TaskExecutionMetadata,
    TaskKey,
    TaskStatus,
    TaskStreamItem,
    TaskUUID,
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
    ) -> tuple[GroupUUID, list[TaskUUID]]: ...

    async def submit_task(
        self,
        execution_metadata: TaskExecutionMetadata,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
        **task_params,
    ) -> TaskUUID: ...

    async def cancel(self, task_or_group_uuid: TaskUUID | GroupUUID) -> None: ...

    async def get_result(self, task_or_group_uuid: TaskUUID | GroupUUID) -> Any: ...

    async def get_status(self, task_or_group_uuid: TaskUUID | GroupUUID) -> TaskStatus | GroupStatus: ...

    async def list_tasks(
        self,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> list[Task]: ...

    async def set_task_progress(self, task_key: TaskKey, report: ProgressReport) -> None: ...

    async def push_task_stream_items(self, task_key: TaskKey, *items: TaskStreamItem) -> None: ...

    async def pull_task_stream_items(
        self,
        task_uuid: TaskUUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[TaskStreamItem], bool, datetime | None]: ...

    async def set_task_stream_done(self, task_key: TaskKey) -> None: ...

    async def set_task_stream_last_update(self, task_key: TaskKey) -> None: ...

    async def task_or_group_exists(self, task_or_group_key: TaskKey | GroupKey) -> bool: ...
