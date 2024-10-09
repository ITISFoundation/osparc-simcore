import logging
from abc import ABC, abstractmethod
from typing import TypeAlias

import dask.typing
from distributed.worker import get_worker
from pydantic import BaseModel, ConfigDict, field_validator

from .protocol import TaskOwner


class BaseTaskEvent(BaseModel, ABC):
    job_id: str
    task_owner: TaskOwner
    msg: str | None = None

    @staticmethod
    @abstractmethod
    def topic_name() -> str:
        raise NotImplementedError

    model_config = ConfigDict(extra="forbid")


def _dask_key_to_dask_task_id(key: dask.typing.Key) -> str:
    if isinstance(key, bytes):
        return key.decode("utf-8")
    if isinstance(key, tuple):
        return "(" + ", ".join(_dask_key_to_dask_task_id(k) for k in key) + ")"
    return f"{key}"


class TaskProgressEvent(BaseTaskEvent):
    progress: float

    @staticmethod
    def topic_name() -> str:
        return "task_progress"

    @classmethod
    def from_dask_worker(
        cls, progress: float, *, task_owner: TaskOwner
    ) -> "TaskProgressEvent":
        worker = get_worker()
        job_id = worker.get_current_task()

        return cls(
            job_id=_dask_key_to_dask_task_id(job_id),
            progress=progress,
            task_owner=task_owner,
        )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job_id": "simcore/services/comp/sleeper:1.1.0:projectid_ec7e595a-63ee-46a1-a04a-901b11b649f8:nodeid_39467d89-b659-4914-9359-c40b1b6d1d6d:uuid_5ee5c655-450d-4711-a3ec-32ffe16bc580",
                    "progress": 0,
                    "task_owner": {
                        "user_id": 32,
                        "project_id": "ec7e595a-63ee-46a1-a04a-901b11b649f8",
                        "node_id": "39467d89-b659-4914-9359-c40b1b6d1d6d",
                        "parent_project_id": None,
                        "parent_node_id": None,
                    },
                },
                {
                    "job_id": "simcore/services/comp/sleeper:1.1.0:projectid_ec7e595a-63ee-46a1-a04a-901b11b649f8:nodeid_39467d89-b659-4914-9359-c40b1b6d1d6d:uuid_5ee5c655-450d-4711-a3ec-32ffe16bc580",
                    "progress": 1.0,
                    "task_owner": {
                        "user_id": 32,
                        "project_id": "ec7e595a-63ee-46a1-a04a-901b11b649f8",
                        "node_id": "39467d89-b659-4914-9359-c40b1b6d1d6d",
                        "parent_project_id": "887e595a-63ee-46a1-a04a-901b11b649f8",
                        "parent_node_id": "aa467d89-b659-4914-9359-c40b1b6d1d6d",
                    },
                },
            ]
        }
    )

    @field_validator("progress")
    @classmethod
    def ensure_between_0_1(cls, v):
        if 0 <= v <= 1:
            return v
        return min(max(0, v), 1)


LogMessageStr: TypeAlias = str
LogLevelInt: TypeAlias = int


class TaskLogEvent(BaseTaskEvent):
    log: LogMessageStr
    log_level: LogLevelInt

    @staticmethod
    def topic_name() -> str:
        return "task_logs"

    @classmethod
    def from_dask_worker(
        cls, log: str, log_level: LogLevelInt, *, task_owner: TaskOwner
    ) -> "TaskLogEvent":
        worker = get_worker()
        job_id = worker.get_current_task()
        return cls(
            job_id=_dask_key_to_dask_task_id(job_id),
            log=log,
            log_level=log_level,
            task_owner=task_owner,
        )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job_id": "simcore/services/comp/sleeper:1.1.0:projectid_ec7e595a-63ee-46a1-a04a-901b11b649f8:nodeid_39467d89-b659-4914-9359-c40b1b6d1d6d:uuid_5ee5c655-450d-4711-a3ec-32ffe16bc580",
                    "log": "some logs",
                    "log_level": logging.INFO,
                    "task_owner": {
                        "user_id": 32,
                        "project_id": "ec7e595a-63ee-46a1-a04a-901b11b649f8",
                        "node_id": "39467d89-b659-4914-9359-c40b1b6d1d6d",
                        "parent_project_id": None,
                        "parent_node_id": None,
                    },
                },
            ]
        }
    )
