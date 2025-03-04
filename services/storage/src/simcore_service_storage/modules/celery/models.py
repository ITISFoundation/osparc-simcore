from enum import StrEnum, auto
from typing import Any, Final, Self, TypeAlias
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel, model_validator

TaskContext: TypeAlias = dict[str, Any]
TaskID: TypeAlias = str
TaskUUID: TypeAlias = UUID

_MIN_PROGRESS: Final[float] = 0.0
_MAX_PROGRESS: Final[float] = 100.0


class TaskState(StrEnum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()
    ABORTED = auto()


class TaskStatus(BaseModel):
    task_uuid: TaskUUID
    task_state: TaskState
    progress_report: ProgressReport

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        value = self.progress_report.actual_value

        valid_states = {
            TaskState.PENDING: value == _MIN_PROGRESS,
            TaskState.RUNNING: _MIN_PROGRESS <= value <= _MAX_PROGRESS,
            TaskState.SUCCESS: value == _MAX_PROGRESS,
            TaskState.ABORTED: value == _MAX_PROGRESS,
            TaskState.FAILURE: value == _MAX_PROGRESS,
        }

        if not valid_states.get(self.task_state, True):
            msg = f"Inconsistent progress actual value for state={self.task_state}: {value}"
            raise ValueError(msg)

        return self
