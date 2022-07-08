import logging
from asyncio import Task
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

TaskName = str
TaskId = str
TaskType = Callable[..., Coroutine[Any, Any, Any]]


class MarkOptions(BaseModel):
    unique: bool = False


class TaskProgress(BaseModel):
    message: str
    percent: float

    def publish(
        self, *, message: Optional[str] = None, percent: Optional[float] = None
    ) -> None:
        """`percent` must be between 0.0 and 1.0 otherwise ValueError is raised"""
        if message:
            self.message = message
        if percent:
            if not (0.0 <= percent <= 1.0):
                raise ValueError(f"{percent=} must be in range [0.0, 1.0]")
            self.percent = percent

        logger.debug("Progress update: %s", f"{self}")

    @classmethod
    def create(cls) -> "TaskProgress":
        return cls.parse_obj(dict(message="", percent=0.0))


class TrackedTask(BaseModel):
    task_id: str
    task: Task
    task_name: TaskName
    task_progress: TaskProgress

    started: datetime = Field(default_factory=datetime.utcnow)
    # have a date when it resulted as completed after a check

    class Config:
        arbitrary_types_allowed = True


class TaskStatus(BaseModel):
    task_progress: TaskProgress
    done: bool
    successful: bool
    started: datetime
