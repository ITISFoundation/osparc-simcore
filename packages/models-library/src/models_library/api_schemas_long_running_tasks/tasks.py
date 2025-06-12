from datetime import datetime
from typing import Any

from pydantic import BaseModel

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


class TaskGet(TaskBase):
    status_href: str
    result_href: str
    abort_href: str
