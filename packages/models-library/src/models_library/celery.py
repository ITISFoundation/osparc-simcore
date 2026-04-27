from datetime import datetime, timedelta
from enum import auto
from typing import Annotated, Any, Final, Literal, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter
from pydantic.config import JsonDict

from .progress_bar import ProgressReport
from .utils.enums import StrAutoEnum

ModelType = TypeVar("ModelType", bound=BaseModel)

type Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

type TaskName = Name
type TaskParams = dict[str, Any]
type TaskID = UUID

type GroupName = Name

DEFAULT_QUEUE: Final[str] = "default"

_TASK_ID_ADAPTER: Final[TypeAdapter[TaskID]] = TypeAdapter(TaskID)


class TaskState(StrAutoEnum):
    PENDING = auto()
    STARTED = auto()
    RETRY = auto()
    SUCCESS = auto()
    FAILURE = auto()


TASK_DONE_STATES: Final[tuple[TaskState, ...]] = (
    TaskState.SUCCESS,
    TaskState.FAILURE,
)


class ExecutorType(StrAutoEnum):
    GROUP = auto()
    GROUP_TASK = auto()
    TASK = auto()


class BaseExecutionMetadata(BaseModel):
    name: TaskName | GroupName
    type: ExecutorType
    description: str | None = None
    ephemeral: bool = True
    queue: str = DEFAULT_QUEUE


class TaskExecutionMetadata(BaseExecutionMetadata):
    name: TaskName
    type: Literal[ExecutorType.TASK] = ExecutorType.TASK


class GroupTaskExecutionMetadata(BaseExecutionMetadata):
    name: TaskName
    type: Literal[ExecutorType.GROUP_TASK] = ExecutorType.GROUP_TASK


class GroupExecutionMetadata(BaseExecutionMetadata):
    name: GroupName
    type: Literal[ExecutorType.GROUP] = ExecutorType.GROUP
    tasks: list[tuple[GroupTaskExecutionMetadata, TaskParams]]


type ExecutionMetadata = Annotated[
    TaskExecutionMetadata | GroupExecutionMetadata | GroupTaskExecutionMetadata,
    Field(discriminator="type"),
]


class TaskStreamItem(BaseModel):
    data: Any


class Task(BaseModel):
    id: TaskID
    metadata: ExecutionMetadata

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "uuid": "123e4567-e89b-12d3-a456-426614174000",
                        "metadata": {
                            "name": "task1",
                            "type": "TASK",
                            "ephemeral": True,
                            "queue": "default",
                        },
                    },
                    {
                        "uuid": "223e4567-e89b-12d3-a456-426614174001",
                        "metadata": {
                            "name": "task2",
                            "type": "GROUP_TASK",
                            "ephemeral": False,
                            "queue": "cpu_bound",
                        },
                    },
                    {
                        "uuid": "323e4567-e89b-12d3-a456-426614174002",
                        "metadata": {"name": "group1", "type": "GROUP", "tasks": []},
                    },
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


class TaskStore(Protocol):
    async def create_group(
        self,
        task_id: TaskID,
        execution_metadata: GroupExecutionMetadata,
        children_task_ids: list[TaskID],
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
        expiry: timedelta,
    ) -> None: ...

    async def create_task(
        self,
        task_id: TaskID,
        execution_metadata: TaskExecutionMetadata,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
        expiry: timedelta,
        index: bool = True,
    ) -> None: ...

    async def task_exists(self, task_id: TaskID) -> bool: ...

    async def get_task_metadata(self, task_id: TaskID) -> ExecutionMetadata | None: ...

    async def get_task_progress(self, task_id: TaskID) -> ProgressReport | None: ...

    async def list_tasks(
        self,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> list[Task]: ...

    async def remove_task(
        self,
        task_id: TaskID,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> None: ...

    async def remove_task_hash(self, task_id: TaskID) -> None:
        """Remove only the task hash from the store, without cleaning sorted-set indexes.

        Stale index entries are cleaned lazily by ``list_tasks``.
        Use this when the owner info is unavailable (e.g. cancel, ephemeral cleanup).
        """

    async def set_task_progress(
        self,
        task_id: TaskID,
        report: ProgressReport,
    ) -> None: ...

    async def set_task_stream_done(self, task_id: TaskID) -> None: ...

    async def set_task_stream_last_update(self, task_id: TaskID) -> None: ...

    async def push_task_stream_items(self, task_id: TaskID, *item: TaskStreamItem) -> None: ...

    async def pull_task_stream_items(
        self, task_id: TaskID, limit: int
    ) -> tuple[list[TaskStreamItem], bool, datetime | None]: ...


class TaskStatus(BaseModel):
    task_id: TaskID
    task_state: TaskState
    progress_report: ProgressReport
    children: list[TaskID] = Field(
        default_factory=list,
        description=("Optional sub-task IDs. Populated only when the task is a celery group; empty for plain tasks."),
    )
    completed_count: int = Field(
        default=0,
        description="Number of completed sub-tasks. Populated only for groups; always 0 for plain tasks.",
    )

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "task_id": "123e4567-e89b-12d3-a456-426614174000",
                        "task_state": "SUCCESS",
                        "progress_report": {
                            "actual_value": 0.5,
                            "total": 1.0,
                            "attempts": 1,
                            "unit": "Byte",
                            "message": {
                                "description": "some description",
                                "current": 12.2,
                                "total": 123,
                            },
                        },
                        "children": [],
                    },
                    {
                        "task_id": "123e4567-e89b-12d3-a456-426614174000",
                        "task_state": "STARTED",
                        "progress_report": {
                            "actual_value": 0.5,
                            "total": 1.0,
                            "attempts": 1,
                            "unit": "Byte",
                        },
                        "children": [
                            "223e4567-e89b-12d3-a456-426614174000",
                            "323e4567-e89b-12d3-a456-426614174000",
                        ],
                    },
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)

    @property
    def is_done(self) -> bool:
        return self.task_state in TASK_DONE_STATES

    @property
    def total_count(self) -> int:
        """Total number of sub-tasks (for groups). Equals 0 for plain tasks."""
        return len(self.children)

    @property
    def is_successful(self) -> bool:
        """``True`` iff the task (or group) reached the ``SUCCESS`` state."""
        return self.task_state == TaskState.SUCCESS
