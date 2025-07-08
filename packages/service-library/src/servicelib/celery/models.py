import datetime
from enum import StrEnum
from typing import Annotated, Protocol, TypeAlias
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel, ConfigDict, StringConstraints

TaskID: TypeAlias = str
TaskName: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
TaskUUID: TypeAlias = UUID


class TaskFilterBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class Task(BaseModel):
    uuid: TaskUUID
    metadata: TaskMetadata


_TASK_DONE = {TaskState.SUCCESS, TaskState.FAILURE, TaskState.ABORTED}


class TaskInfoStore(Protocol):
    async def create_task(
        self,
        task_id: TaskID,
        task_metadata: TaskMetadata,
        expiry: datetime.timedelta,
    ) -> None: ...

    async def exists_task(self, task_id: TaskID) -> bool: ...

    async def get_task_metadata(self, task_id: TaskID) -> TaskMetadata | None: ...

    async def get_task_progress(self, task_id: TaskID) -> ProgressReport | None: ...

    async def list_tasks(self, task_context: TaskFilterBase) -> list[Task]: ...

    async def remove_task(self, task_id: TaskID) -> None: ...

    async def set_task_progress(
        self, task_id: TaskID, report: ProgressReport
    ) -> None: ...


class TaskStatus(BaseModel):
    task_uuid: TaskUUID
    task_state: TaskState
    progress_report: ProgressReport

    @property
    def is_done(self) -> bool:
        return self.task_state in _TASK_DONE
