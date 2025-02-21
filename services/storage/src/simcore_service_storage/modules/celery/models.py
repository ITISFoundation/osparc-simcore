from typing import TypeAlias

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel

TaskID: TypeAlias = str


class TaskStatus(BaseModel):
    task_id: str
    task_state: str  # add enum
    progress_report: ProgressReport | None = None
