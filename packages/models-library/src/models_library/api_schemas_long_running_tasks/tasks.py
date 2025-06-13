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

    # NOTE: task name can always be extraced from the task_id
    # since it'e encoded inside it
    task_name: str = ""

    @field_validator("task_name", mode="before")
    @classmethod
    def populate_task_name(cls, task_id, info):
        task_name = task_id

        # attempt to solve the task name from the task_id
        # if this is coming form a long_running_task
        task_id = info.data.get("task_id")
        if task_id:
            parts = task_id.split(".")
            if len(parts) >= 2:
                task_name = parts[1]

        return urllib.parse.unquote(task_name)


class TaskGet(TaskBase):
    status_href: str
    result_href: str
    abort_href: str
