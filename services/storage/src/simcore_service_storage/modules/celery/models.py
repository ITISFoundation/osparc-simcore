from enum import StrEnum, auto
from typing import Any, Self, TypeAlias
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel, model_validator

TaskContext: TypeAlias = dict[str, Any]
TaskID: TypeAlias = str
TaskUUID: TypeAlias = UUID


class TaskState(StrEnum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    ERROR = auto()
    ABORTED = auto()


_TASK_DONE = {TaskState.SUCCESS, TaskState.ERROR, TaskState.ABORTED}


class TaskStatus(BaseModel):
    task_uuid: TaskUUID
    task_state: TaskState
    progress_report: ProgressReport

    @property
    def is_done(self) -> bool:
        return self.task_state in _TASK_DONE

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        value = self.progress_report.actual_value
        min_value = 0.0
        max_value = self.progress_report.total

        valid_states = {
            TaskState.PENDING: value == min_value,
            TaskState.RUNNING: min_value <= value <= max_value,
            TaskState.SUCCESS: value == max_value,
            TaskState.ABORTED: value == max_value,
            TaskState.ERROR: value == max_value,
        }

        if not valid_states.get(self.task_state, True):
            msg = f"Inconsistent progress actual value for state={self.task_state}: {value}"
            raise ValueError(msg)

        return self


class TaskError(BaseModel):
    exc_type: str
    exc_msg: str


TaskId: TypeAlias = str
