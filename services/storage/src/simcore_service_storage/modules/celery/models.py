from enum import StrEnum, auto
from typing import Any, TypeAlias
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel

TaskContext: TypeAlias = dict[str, Any]
TaskID: TypeAlias = str
TaskUUID: TypeAlias = UUID


class TaskState(StrEnum):
    PENDING = auto()
    STARTED = auto()
    PROGRESS = auto()
    SUCCESS = auto()
    FAILURE = auto()
    ABORTED = auto()


class TaskStatus(BaseModel):
    task_uuid: TaskUUID
    task_state: TaskState
    progress_report: ProgressReport | None = None
