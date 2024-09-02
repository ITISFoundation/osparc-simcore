import urllib.parse
from datetime import datetime
from typing import Any

from pydantic import BaseModel, validator

from ..progress_bar import ProgressReport
from .base import TaskId


class TaskStatus(BaseModel):
    progress_report: ProgressReport | None
    done: bool
    started: datetime


class TaskResult(BaseModel):
    result: Any | None
    error: Any | None


class TaskGet(BaseModel):
    task_id: TaskId
    task_name: str
    status_href: str
    result_href: str
    abort_href: str

    @validator("task_name")
    @classmethod
    def unquote_str(cls, v) -> str:
        return urllib.parse.unquote(v)
