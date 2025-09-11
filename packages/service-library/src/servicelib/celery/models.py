import datetime
from enum import StrEnum
from typing import Annotated, Any, Final, Literal, Protocol, Self, TypeAlias, TypeVar
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from pydantic.config import JsonDict

T = TypeVar("T", bound=BaseModel)

TaskID: TypeAlias = str
TaskName: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
TaskUUID: TypeAlias = UUID
_TASK_ID_KEY_DELIMITATOR: Final[str] = ":"
WILDCARD: Final[str] = "*"


class TaskFilter(BaseModel):
    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _check_valid_filters(self) -> Self:
        for key in self.model_dump().keys():
            if _TASK_ID_KEY_DELIMITATOR in key or "=" in key:
                raise ValueError(f"Invalid filter key: '{key}'")
            if (
                _TASK_ID_KEY_DELIMITATOR in f"{getattr(self, key)}"
                or "=" in f"{getattr(self, key)}"
            ):
                raise ValueError(
                    f"Invalid filter value for key '{key}': '{getattr(self, key)}'"
                )
        return self

    def _build_task_id_prefix(self) -> str:
        filter_dict = self.model_dump()
        return _TASK_ID_KEY_DELIMITATOR.join(
            [f"{key}={filter_dict[key]}" for key in sorted(filter_dict)]
        )

    def task_id(self, task_uuid: TaskUUID | Literal["*"]) -> TaskID:
        return _TASK_ID_KEY_DELIMITATOR.join(
            [self._build_task_id_prefix(), f"task_uuid={task_uuid}"]
        )

    @classmethod
    def recreate_model(cls, task_id: TaskID, model: type[T]) -> T:
        filter_dict = cls.recreate_data(task_id)
        return model.model_validate(filter_dict)

    @classmethod
    def recreate_data(cls, task_id: TaskID) -> dict[str, Any]:
        """Recreates the filter data from a task_id string
        Careful: does not validate types. For that use `recreate_model` instead
        """
        try:
            parts = task_id.split(_TASK_ID_KEY_DELIMITATOR)
            return {
                key: value
                for part in parts[:-1]
                if (key := part.split("=")[0]) and (value := part.split("=")[1])
            }
        except (IndexError, ValueError) as err:
            raise ValueError(f"Invalid task_id format: {task_id}") from err

    @classmethod
    def task_uuid(cls, task_id: TaskID) -> TaskUUID:
        try:
            return UUID(task_id.split(_TASK_ID_KEY_DELIMITATOR)[-1].split("=")[1])
        except (IndexError, ValueError) as err:
            raise ValueError(f"Invalid task_id format: {task_id}") from err


class TaskState(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ABORTED = "ABORTED"


class TasksQueue(StrEnum):
    CPU_BOUND = "cpu_bound"
    DEFAULT = "default"
    API_WORKER_QUEUE = "api_worker_queue"


class TaskMetadata(BaseModel):
    name: TaskName
    ephemeral: bool = True
    queue: TasksQueue = TasksQueue.DEFAULT


class Task(BaseModel):
    uuid: TaskUUID
    metadata: TaskMetadata

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "uuid": "123e4567-e89b-12d3-a456-426614174000",
                        "metadata": {
                            "name": "task1",
                            "ephemeral": True,
                            "queue": "default",
                        },
                    },
                    {
                        "uuid": "223e4567-e89b-12d3-a456-426614174001",
                        "metadata": {
                            "name": "task2",
                            "ephemeral": False,
                            "queue": "cpu_bound",
                        },
                    },
                    {
                        "uuid": "323e4567-e89b-12d3-a456-426614174002",
                        "metadata": {
                            "name": "task3",
                            "ephemeral": True,
                            "queue": "default",
                        },
                    },
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


_TASK_DONE = {TaskState.SUCCESS, TaskState.FAILURE, TaskState.ABORTED}


class TaskInfoStore(Protocol):
    async def create_task(
        self,
        task_id: TaskID,
        task_metadata: TaskMetadata,
        expiry: datetime.timedelta,
    ) -> None: ...

    async def exists_task(self, task_id: TaskID) -> bool: ...

    async def get_task_metadata(self, task_id: TaskID) -> TaskMetadata | None: ...

    async def get_task_progress(self, task_id: TaskID) -> ProgressReport | None: ...

    async def list_tasks(self, task_context: TaskFilter) -> list[Task]: ...

    async def remove_task(self, task_id: TaskID) -> None: ...

    async def set_task_progress(
        self, task_id: TaskID, report: ProgressReport
    ) -> None: ...


class TaskStatus(BaseModel):
    task_uuid: TaskUUID
    task_state: TaskState
    progress_report: ProgressReport

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:

        schema.update(
            {
                "examples": [
                    {
                        "task_uuid": "123e4567-e89b-12d3-a456-426614174000",
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
                    }
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)

    @property
    def is_done(self) -> bool:
        return self.task_state in _TASK_DONE
