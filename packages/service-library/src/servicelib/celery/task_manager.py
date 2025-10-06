from typing import Any, Protocol, runtime_checkable

from models_library.progress_bar import ProgressReport

from .models import (
    ExecutionMetadata,
    OwnerMetadata,
    Task,
    TaskKey,
    TaskStatus,
    TaskUUID,
)


@runtime_checkable
class TaskManager(Protocol):
    async def submit_task(
        self,
        execution_metadata: ExecutionMetadata,
        *,
        owner_metadata: OwnerMetadata,
        **task_param
    ) -> TaskUUID: ...

    async def cancel_task(
        self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID
    ) -> None: ...

    async def get_task_result(
        self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID
    ) -> Any: ...

    async def get_task_status(
        self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID
    ) -> TaskStatus: ...

    async def list_tasks(self, owner_metadata: OwnerMetadata) -> list[Task]: ...

    async def set_task_progress(
        self, task_key: TaskKey, report: ProgressReport
    ) -> None: ...

    async def push_task_result(self, task_key: TaskKey, result: str) -> None: ...

    async def pull_task_results(
        self,
        owner_metadata: OwnerMetadata,
        task_uuid: TaskUUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[str], int, bool]: ...

    async def task_exists(self, task_key: TaskKey) -> bool: ...
