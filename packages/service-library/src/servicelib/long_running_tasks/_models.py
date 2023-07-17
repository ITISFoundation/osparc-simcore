from asyncio import Task
from datetime import datetime
from typing import Any, Awaitable, Callable, Coroutine

from models_library.api_schemas_long_running_tasks.base import (
    ProgressMessage,
    ProgressPercent,
    TaskId,
)
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskProgress,
    TaskResult,
    TaskStatus,
)
from pydantic import BaseModel, Field, PositiveFloat

TaskName = str

TaskType = Callable[..., Coroutine[Any, Any, Any]]

ProgressCallback = Callable[[ProgressMessage, ProgressPercent, TaskId], Awaitable[None]]


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

    started: datetime = Field(default_factory=datetime.utcnow)
    last_status_check: datetime | None = Field(
        default=None,
        description=(
            "used to detect when if the task is not actively "
            "polled by the client who created it"
        ),
    )

    class Config:
        arbitrary_types_allowed = True


class ClientConfiguration(BaseModel):
    router_prefix: str
    default_timeout: PositiveFloat


# explicit export of models for api-schemas

assert TaskResult  # nosec
assert TaskGet  # nosec
assert TaskStatus  # nosec

__all__: tuple[str, ...] = (
    "TaskGet",
    "TaskId",
    "TaskResult",
    "TaskStatus",
)
