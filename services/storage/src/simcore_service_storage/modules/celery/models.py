from datetime import timedelta
from enum import StrEnum, auto
from typing import Any, Final, Protocol, TypeAlias
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel

TaskContext: TypeAlias = dict[str, Any]
TaskID: TypeAlias = str
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
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    ERROR = auto()
    ABORTED = auto()


class TaskMetadata(BaseModel):
    ephemeral: bool = True
    queue: str = "default"


_TASK_DONE = {TaskState.SUCCESS, TaskState.ERROR, TaskState.ABORTED}


class TaskMetadataStore(Protocol):
    async def exists(self, task_id: TaskID) -> bool: ...

    async def get(self, task_id: TaskID) -> TaskMetadata | None: ...

    async def get_uuids(self, task_context: TaskContext) -> set[TaskUUID]: ...

    async def remove(self, task_id: TaskID) -> None: ...

    async def set(
        self, task_id: TaskID, task_data: TaskMetadata, expiry: timedelta
    ) -> None: ...


class TaskStatus(BaseModel):
    task_uuid: TaskUUID
    task_state: TaskState
    progress_report: ProgressReport

    @property
    def is_done(self) -> bool:
        return self.task_state in _TASK_DONE


class TaskError(BaseModel):
    exc_type: str
    exc_msg: str


TaskId: TypeAlias = str
