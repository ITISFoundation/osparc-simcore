import urllib.parse
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from .base import TaskId, TaskProgress


class TaskStatus(BaseModel):
    task_progress: TaskProgress
    done: bool
    started: datetime | None


class TaskResult(BaseModel):
    result: Any | None
    error: Any | None


class TaskBase(BaseModel):
    task_id: TaskId
    task_name: str


class TaskGet(TaskBase):
    status_href: str
    result_href: str
    abort_href: str

    @field_validator("task_name")
    @classmethod
    def unquote_str(cls, v) -> str:
        return urllib.parse.unquote(v)
