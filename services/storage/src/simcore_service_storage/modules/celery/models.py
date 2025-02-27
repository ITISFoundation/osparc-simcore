from typing import Any, TypeAlias
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel

TaskContext: TypeAlias = dict[str, Any]
TaskID: TypeAlias = str
TaskUUID: TypeAlias = UUID


class TaskStatus(BaseModel):
    task_uuid: TaskUUID
    task_state: str  # add enum
    progress_report: ProgressReport | None = None
