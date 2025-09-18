import datetime
from enum import StrEnum
from typing import Annotated, Any, Final, Protocol, Self, TypeAlias, TypeVar
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from pydantic.config import JsonDict

ModelType = TypeVar("ModelType", bound=BaseModel)

TaskID: TypeAlias = str
TaskName: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
TaskUUID: TypeAlias = UUID
_TASK_ID_KEY_DELIMITATOR: Final[str] = ":"
_WILDCARD: Final[str] = "*"
_FORBIDDEN_CHARS = (_WILDCARD, _TASK_ID_KEY_DELIMITATOR, "=")


class Wildcard:
    def __str__(self) -> str:
        return _WILDCARD


class OwnerMetadata(BaseModel):
    """
    Class for associating metadata with a celery task. The implementation is very flexible and allows the task owner to define their own metadata.
    This could be metadata for validating if a user has access to a given task (e.g. user_id or product_name) or metadata for keeping track of how to handle a task,
    e.g. which schema will the result of the task have.

    The class exposes a filtering mechanism to list tasks using wildcards.

    Example usage:
        class StorageOwnerMetadata(OwnerMetadata):
            user_id: int | Wildcard
            product_name: int | Wildcard
            owner = "storage-service"

        Listing tasks using the filter `StorageOwnerMetadata(user_id=123, product_name=Wildcard())` will return all tasks with
        user_id 123, any product_name submitted from storage-service.

    If the metadata schema is known, the class allows deserializing the metadata (recreate_as_model). I.e. one can recover the metadata from the task:
        metadata -> task_uuid -> metadata

    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    owner: Annotated[str, StringConstraints(min_length=1, pattern=r"^[a-z_-]+$")]

    @model_validator(mode="after")
    def _check_valid_filters(self) -> Self:
        for key, value in self.model_dump().items():
            # forbidden keys
            if any(x in key for x in _FORBIDDEN_CHARS):
                raise ValueError(f"Invalid filter key: '{key}'")
            # forbidden values
            if not isinstance(value, Wildcard) and any(
                x in f"{value}" for x in _FORBIDDEN_CHARS
            ):
                raise ValueError(f"Invalid filter value for key '{key}': '{value}'")
        return self

    def _build_task_id_prefix(self) -> str:
        filter_dict = self.model_dump()
        return _TASK_ID_KEY_DELIMITATOR.join(
            [f"{key}={filter_dict[key]}" for key in sorted(filter_dict)]
        )

    def create_task_id(self, task_uuid: TaskUUID | Wildcard) -> TaskID:
        return _TASK_ID_KEY_DELIMITATOR.join(
            [
                self._build_task_id_prefix(),
                f"task_uuid={task_uuid}",
            ]
        )

    @classmethod
    def recreate_as_model(cls, task_id: TaskID, schema: type[ModelType]) -> ModelType:
        filter_dict = cls._recreate_data(task_id)
        return schema.model_validate(filter_dict)

    @classmethod
    def _recreate_data(cls, task_id: TaskID) -> dict[str, Any]:
        """Recreates the filter data from a task_id string
        WARNING: does not validate types. For that use `recreate_model` instead
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
    def get_task_uuid(cls, task_id: TaskID) -> TaskUUID:
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


TASK_DONE_STATES: Final[tuple[TaskState, ...]] = (
    TaskState.SUCCESS,
    TaskState.FAILURE,
)


class TasksQueue(StrEnum):
    CPU_BOUND = "cpu_bound"
    DEFAULT = "default"
    API_WORKER_QUEUE = "api_worker_queue"


class ExecutionMetadata(BaseModel):
    name: TaskName
    ephemeral: bool = True
    queue: TasksQueue = TasksQueue.DEFAULT


class Task(BaseModel):
    uuid: TaskUUID
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


class TaskInfoStore(Protocol):
    async def create_task(
        self,
        task_id: TaskID,
        task_metadata: ExecutionMetadata,
        expiry: datetime.timedelta,
    ) -> None: ...

    async def task_exists(self, task_id: TaskID) -> bool: ...

    async def get_task_metadata(self, task_id: TaskID) -> ExecutionMetadata | None: ...

    async def get_task_progress(self, task_id: TaskID) -> ProgressReport | None: ...

    async def list_tasks(self, task_filter: OwnerMetadata) -> list[Task]: ...

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
        return self.task_state in TASK_DONE_STATES
