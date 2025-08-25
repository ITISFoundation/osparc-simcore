import urllib.parse
from datetime import datetime
from typing import Any

from common_library.exclude import Unset
from pydantic import BaseModel, ConfigDict, model_validator

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
    task_name: str | Unset = Unset.VALUE

    @model_validator(mode="after")
    def try_populate_task_name_from_task_id(self) -> "TaskBase":
        # NOTE: currently this model is used to validate tasks coming from
        # the celery backend and form long_running_tasks
        # 1. if a task comes from Celery, it will keep it's given name
        # 2. if a task comes from long_running_tasks, it will extract it form
        #   the task_id, which looks like "{PREFIX}.{TASK_NAME}.UNIQUE|{UUID}"

        if self.task_id and self.task_name == Unset.VALUE:
            parts = self.task_id.split(".")
            if len(parts) > 1:
                self.task_name = urllib.parse.unquote(parts[1])

        if self.task_name == Unset.VALUE:
            self.task_name = self.task_id

        return self

    model_config = ConfigDict(arbitrary_types_allowed=True)


class TaskGet(TaskBase):
    status_href: str
    result_href: str
    abort_href: str
