from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Final, Literal, Protocol, Self, TypeAlias, TypeVar
from uuid import UUID

import orjson
from common_library.json_serialization import json_dumps, json_loads
from models_library.progress_bar import ProgressReport
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.config import JsonDict

ModelType = TypeVar("ModelType", bound=BaseModel)

TaskKey: TypeAlias = str
TaskName: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
TaskUUID: TypeAlias = UUID
_TASK_ID_KEY_DELIMITATOR: Final[str] = ":"
_FORBIDDEN_KEY_CHARS = ("*", _TASK_ID_KEY_DELIMITATOR, "=")
_FORBIDDEN_VALUE_CHARS = (_TASK_ID_KEY_DELIMITATOR, "=")
AllowedTypes = (
    int | float | bool | str | None | list[str] | list[int] | list[float] | list[bool]
)

Wildcard: TypeAlias = Literal["*"]
WILDCARD: Final[Wildcard] = "*"

_TASK_UUID_KEY: Final[str] = "task_uuid"


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
            owner = APP_NAME

        Where APP_NAME is the name of the service. Listing tasks using the filter
        `StorageOwnerMetadata(user_id=123, product_name=WILDCARD)` will return all tasks with
        user_id 123, any product_name submitted from the service.

    If the metadata schema is known, the class allows deserializing the metadata (recreate_as_model). I.e. one can recover the metadata from the task:
        metadata -> task_uuid -> metadata

    """

    model_config = ConfigDict(extra="allow", frozen=True)
    owner: Annotated[
        str,
        StringConstraints(min_length=1, pattern=r"^[a-z_-]+$"),
        Field(
            description='Identifies the service owning the task. Should be the "APP_NAME" of the service.'
        ),
    ]

    @model_validator(mode="after")
    def _check_valid_filters(self) -> Self:
        for key, value in self.model_dump().items():
            # forbidden key chars
            if any(x in key for x in _FORBIDDEN_KEY_CHARS):
                raise ValueError(f"Invalid filter key: '{key}'")
            # forbidden value chars
            if any(x in json_dumps(value) for x in _FORBIDDEN_VALUE_CHARS):
                raise ValueError(f"Invalid filter value for key '{key}': '{value}'")

        if _TASK_UUID_KEY in self.model_dump():
            raise ValueError(f"'{_TASK_UUID_KEY}' is a reserved key")

        class _TypeValidationModel(BaseModel):
            filters: dict[str, AllowedTypes]

        _TypeValidationModel.model_validate({"filters": self.model_dump()})
        return self

    def model_dump_task_key(self, task_uuid: TaskUUID | Wildcard) -> TaskKey:
        data = self.model_dump(mode="json")
        data.update({_TASK_UUID_KEY: f"{task_uuid}"})
        return _TASK_ID_KEY_DELIMITATOR.join(
            [f"{k}={json_dumps(v)}" for k, v in sorted(data.items())]
        )

    @classmethod
    def model_validate_task_key(cls, task_key: TaskKey) -> Self:
        data = cls._deserialize_task_key(task_key)
        data.pop(_TASK_UUID_KEY, None)
        return cls.model_validate(data)

    @classmethod
    def _deserialize_task_key(cls, task_key: TaskKey) -> dict[str, AllowedTypes]:
        key_value_pairs = [
            item.split("=") for item in task_key.split(_TASK_ID_KEY_DELIMITATOR)
        ]
        try:
            return {key: json_loads(value) for key, value in key_value_pairs}
        except orjson.JSONDecodeError as err:
            raise ValueError(f"Invalid task_id format: {task_key}") from err

    @classmethod
    def get_task_uuid(cls, task_key: TaskKey) -> TaskUUID:
        data = cls._deserialize_task_key(task_key)
        try:
            uuid_string = data.get(_TASK_UUID_KEY)
            if not isinstance(uuid_string, str):
                raise ValueError(f"Invalid task_id format: {task_key}")
            return TaskUUID(uuid_string)
        except ValueError as err:
            raise ValueError(f"Invalid task_id format: {task_key}") from err


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


class TaskStreamItem(BaseModel):
    data: Any


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


class TaskStore(Protocol):
    async def create_task(
        self,
        task_key: TaskKey,
        execution_metadata: ExecutionMetadata,
        expiry: timedelta,
    ) -> None: ...

    async def task_exists(self, task_key: TaskKey) -> bool: ...

    async def get_task_metadata(
        self, task_key: TaskKey
    ) -> ExecutionMetadata | None: ...

    async def get_task_progress(self, task_key: TaskKey) -> ProgressReport | None: ...

    async def list_tasks(self, owner_metadata: OwnerMetadata) -> list[Task]: ...

    async def remove_task(self, task_key: TaskKey) -> None: ...

    async def set_task_progress(
        self,
        task_key: TaskKey,
        report: ProgressReport,
    ) -> None: ...

    async def set_task_stream_done(self, task_key: TaskKey) -> None: ...

    async def set_task_stream_last_update(self, task_key: TaskKey) -> None: ...

    async def push_task_stream_items(
        self, task_key: TaskKey, *item: TaskStreamItem
    ) -> None: ...

    async def pull_task_stream_items(
        self, task_key: TaskKey, limit: int
    ) -> tuple[list[TaskStreamItem], bool, datetime | None]: ...


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
