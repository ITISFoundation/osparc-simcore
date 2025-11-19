# mypy: disable-error-code=truthy-function
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, TypeAlias

from common_library.basic_types import DEFAULT_FACTORY
from models_library.api_schemas_long_running_tasks.base import (
    ProgressMessage,
    ProgressPercent,
    TaskId,
    TaskProgress,
)
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskBase,
    TaskGet,
    TaskResult,
    TaskStatus,
)
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, model_validator

TaskType: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]

ProgressCallback: TypeAlias = Callable[
    [ProgressMessage, ProgressPercent | None, TaskId], Awaitable[None]
]

RequestBody: TypeAlias = Any
TaskContext: TypeAlias = dict[str, Any]

LRTNamespace: TypeAlias = str

RegisteredTaskName: TypeAlias = str


class ResultField(BaseModel):
    str_result: str | None = None
    str_error: str | None = None

    @model_validator(mode="after")
    def validate_mutually_exclusive(self) -> "ResultField":
        if self.str_result is not None and self.str_error is not None:
            msg = "Cannot set both 'result' and 'error' - they are mutually exclusive"
            raise ValueError(msg)
        return self


class TaskData(BaseModel):
    registered_task_name: RegisteredTaskName
    task_id: str
    task_progress: TaskProgress
    # NOTE: this context lifetime is with the tracked task (similar to aiohttp storage concept)
    task_context: TaskContext
    fire_and_forget: Annotated[
        bool,
        Field(
            description="if True then the task will not be auto-cancelled if no one enquires of its status"
        ),
    ]

    started: Annotated[datetime, Field(default_factory=lambda: datetime.now(UTC))] = (
        DEFAULT_FACTORY
    )
    last_status_check: Annotated[
        datetime | None,
        Field(
            description=(
                "used to detect when if the task is not actively "
                "polled by the client who created it"
            )
        ),
    ] = None

    detected_as_done_at: Annotated[
        datetime | None,
        Field(
            description=(
                "used to remove the task when it's first detected as done "
                "if a task was started as fire_and_forget=True"
            )
        ),
    ] = None

    is_done: Annotated[
        bool,
        Field(description="True when the task finished running with or without errors"),
    ] = False
    result_field: Annotated[
        ResultField | None, Field(description="the result of the task")
    ] = None
    marked_for_removal: Annotated[
        bool,
        Field(description=("if True, indicates the task is marked for removal")),
    ] = False
    marked_for_removal_at: Annotated[
        datetime | None,
        Field(
            description=(
                "In some cases we have an entry in Redis but no task to remove, to ensure "
                "proper cleanup, wait some time after the marke_for_remval and then remove "
                "the entry form Redis"
            )
        ),
    ] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "examples": [
                {
                    "registered_task_name": "a-task-name",
                    "task_id": "1a119618-7186-4bc1-b8de-7e3ff314cb7e",
                    "task_name": "running-task",
                    "task_status": "running",
                    "task_progress": {
                        "task_id": "1a119618-7186-4bc1-b8de-7e3ff314cb7e"
                    },
                    "task_context": {"key": "value"},
                    "fire_and_forget": False,
                }
            ]
        },
    )


class ClientConfiguration(BaseModel):
    router_prefix: str
    default_timeout: PositiveFloat


@dataclass(frozen=True)
class LRTask:
    progress: TaskProgress
    _result: Coroutine[Any, Any, Any] | None = None

    def done(self) -> bool:
        return self._result is not None

    async def result(self) -> Any:
        if not self._result:
            msg = "No result ready!"
            raise ValueError(msg)
        return await self._result


__all__: tuple[str, ...] = (
    "ProgressMessage",
    "ProgressPercent",
    "TaskBase",
    "TaskGet",
    "TaskId",
    "TaskProgress",
    "TaskResult",
    "TaskStatus",
)

# nopycln: file
