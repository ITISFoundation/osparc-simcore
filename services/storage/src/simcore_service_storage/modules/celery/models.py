from datetime import timedelta
from enum import StrEnum
from typing import Any, Final, Protocol, TypeAlias
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel

TaskContext: TypeAlias = dict[str, Any]
TaskID: TypeAlias = str
TaskName: TypeAlias = str
TaskUUID: TypeAlias = UUID

_CELERY_TASK_ID_KEY_SEPARATOR: Final[str] = ":"


def build_task_id_prefix(task_context: TaskContext) -> str:
    return _CELERY_TASK_ID_KEY_SEPARATOR.join(
        [f"{task_context[key]}" for key in sorted(task_context)]
    )


def build_task_id(task_context: TaskContext, task_uuid: TaskUUID) -> TaskID:
    return _CELERY_TASK_ID_KEY_SEPARATOR.join(
        [build_task_id_prefix(task_context), f"{task_uuid}"]
    )


class TaskState(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ABORTED = "ABORTED"


class TasksQueue(StrEnum):
    CPU_BOUND = "cpu_bound"
    DEFAULT = "default"


class TaskMetadata(BaseModel):
    name: TaskName
    ephemeral: bool = True
    queue: TasksQueue = TasksQueue.DEFAULT


_TASK_DONE = {TaskState.SUCCESS, TaskState.FAILURE, TaskState.ABORTED}


class TaskInfoStore(Protocol):
    async def create(
        self,
        task_context: TaskContext,
        task_uuid: TaskUUID,
        task_metadata: TaskMetadata,
        expiry: timedelta,
    ) -> None: ...

    async def exists(self, task_context: TaskContext, task_uuid: TaskUUID) -> bool: ...

    async def get_metadata(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> TaskMetadata | None: ...

    async def get_progress(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> ProgressReport | None: ...

    async def get_uuids(self, task_context: TaskContext) -> set[TaskUUID]: ...

    async def remove(self, task_context: TaskContext, task_uuid: TaskUUID) -> None: ...

    async def set_progress(
        self, task_context: TaskContext, task_uuid: TaskUUID, report: ProgressReport
    ) -> None: ...


class TaskStatus(BaseModel):
    task_uuid: TaskUUID
    task_state: TaskState
    progress_report: ProgressReport

    @property
    def is_done(self) -> bool:
        return self.task_state in _TASK_DONE


TaskId: TypeAlias = str
