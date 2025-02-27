from typing import Any, TypeAlias

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel

TaskID: TypeAlias = str
TaskContext: TypeAlias = dict[str, Any]


class TaskStatus(BaseModel):
    task_id: str
    task_state: str  # add enum
    progress_report: ProgressReport | None = None
