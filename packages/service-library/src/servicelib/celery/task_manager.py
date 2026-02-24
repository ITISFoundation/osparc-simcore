from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from models_library.progress_bar import ProgressReport

from .models import (
    ExecutionMetadata,
    GroupKey,
    GroupStatus,
    GroupUUID,
    OwnerMetadata,
    Status,
    Task,
    TaskKey,
    TaskParams,
    TaskStatus,
    TaskStreamItem,
    TaskUUID,
)


@runtime_checkable
class TaskManager(Protocol):
    async def submit_group(
        self,
        executions: list[tuple[ExecutionMetadata, TaskParams]],
        *,
        owner_metadata: OwnerMetadata,
    ) -> tuple[GroupUUID, list[TaskUUID]]: ...

    async def submit_task(
        self, execution_metadata: ExecutionMetadata, *, owner_metadata: OwnerMetadata, **task_params
    ) -> TaskUUID: ...

    async def cancel_task(self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID) -> None: ...

    async def get_task_result(self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID) -> Any: ...

    async def get_task_status(self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID) -> TaskStatus: ...

    async def get_group_status(self, owner_metadata: OwnerMetadata, group_uuid: GroupUUID) -> GroupStatus: ...

    async def get_status(self, owner_metadata: OwnerMetadata, task_or_group_uuid: TaskUUID | GroupUUID) -> Status: ...

    async def list_tasks(self, owner_metadata: OwnerMetadata) -> list[Task]: ...

    async def set_task_progress(self, task_key: TaskKey, report: ProgressReport) -> None: ...

    async def push_task_stream_items(self, task_key: TaskKey, *items: TaskStreamItem) -> None: ...

    async def pull_task_stream_items(
        self,
        owner_metadata: OwnerMetadata,
        task_uuid: TaskUUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[TaskStreamItem], bool, datetime | None]: ...

    async def set_task_stream_done(self, task_key: TaskKey) -> None: ...

    async def set_task_stream_last_update(self, task_key: TaskKey) -> None: ...

    async def task_or_group_exists(self, task_or_group_key: TaskKey | GroupKey) -> bool: ...
