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


class ResultField(BaseModel):
    result: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_mutually_exclusive(self) -> "ResultField":
        if self.result is not None and self.error is not None:
            msg = "Cannot set both 'result' and 'error' - they are mutually exclusive"
            raise ValueError(msg)
        return self


class TaskData(BaseModel):
    task_id: str
    task_progress: TaskProgress
    # NOTE: this context lifetime is with the tracked task (similar to aiohttp storage concept)
    task_context: dict[str, Any]
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

    is_done: Annotated[
        bool,
        Field(description="True when the task finished running with or without errors"),
    ] = False
    result_field: Annotated[
        ResultField | None, Field(description="the result of the task")
    ] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "examples": [
                {
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
