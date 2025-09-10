import datetime
from enum import StrEnum
from typing import Annotated, Protocol, TypeAlias
from uuid import UUID

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel, ConfigDict, StringConstraints
from pydantic.config import JsonDict

TaskID: TypeAlias = str
TaskName: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
TaskUUID: TypeAlias = UUID


class TaskFilter(BaseModel): ...


class TaskState(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ABORTED = "ABORTED"


TASK_FINAL_STATES = {TaskState.SUCCESS, TaskState.FAILURE, TaskState.ABORTED}


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
        return self.task_state in TASK_FINAL_STATES
