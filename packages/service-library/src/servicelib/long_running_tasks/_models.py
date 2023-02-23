import logging
import urllib.parse
from asyncio import Task
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Coroutine, Optional

from pydantic import (
    BaseModel,
    Field,
    PositiveFloat,
    confloat,
    validate_arguments,
    validator,
)

logger = logging.getLogger(__name__)

TaskName = str
TaskId = str
TaskType = Callable[..., Coroutine[Any, Any, Any]]

ProgressMessage = str
ProgressPercent = confloat(ge=0.0, le=1.0)
ProgressCallback = Callable[[ProgressMessage, ProgressPercent, TaskId], Awaitable[None]]


class MarkOptions(BaseModel):
    unique: bool = False


class TaskProgress(BaseModel):
    """
    Helps the user to keep track of the progress. Progress is expected to be
    defined as a float bound between 0.0 and 1.0
    """

    message: ProgressMessage = Field(default="")
    percent: ProgressPercent = Field(default=0.0)

    @validate_arguments
    def update(
        self,
        *,
        message: Optional[ProgressMessage] = None,
        percent: Optional[ProgressPercent] = None,
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

    @validator("percent")
    @classmethod
    def round_value_to_3_digit(cls, v):
        return round(v, 3)


class TrackedTask(BaseModel):
    task_id: str
    task: Task
    task_name: TaskName
    task_progress: TaskProgress
    # NOTE: this context lifetime is with the tracked task (similar to aiohttp storage concept)
    task_context: dict[str, Any]
    fire_and_forget: bool = Field(
        ...,
        description="if True then the task will not be auto-cancelled if no one enquires of its status",
    )

    started: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    last_status_check: Optional[datetime] = Field(
        default=None,
        description=(
            "used to detect when if the task is not actively "
            "polled by the client who created it"
        ),
    )

    class Config:
        arbitrary_types_allowed = True


class TaskStatus(BaseModel):
    task_progress: TaskProgress
    done: bool
    started: datetime


class TaskResult(BaseModel):
    result: Optional[Any]
    error: Optional[Any]


class ClientConfiguration(BaseModel):
    router_prefix: str
    default_timeout: PositiveFloat


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
