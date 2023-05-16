import logging
from abc import ABC, abstractmethod
from typing import TypeAlias, Union

from distributed.worker import get_worker
from pydantic import BaseModel, Extra, NonNegativeFloat


class BaseTaskEvent(BaseModel, ABC):
    job_id: str
    msg: str | None = None

    @staticmethod
    @abstractmethod
    def topic_name() -> str:
        raise NotImplementedError

    class Config:
        extra = Extra.forbid


class TaskProgressEvent(BaseTaskEvent):
    progress: NonNegativeFloat

    @staticmethod
    def topic_name() -> str:
        return "task_progress"

    @classmethod
    def from_dask_worker(cls, progress: float) -> "TaskProgressEvent":
        return cls(job_id=get_worker().get_current_task(), progress=progress)

    class Config(BaseTaskEvent.Config):
        schema_extra = {
            "examples": [
                {
                    "job_id": "simcore/services/comp/sleeper:1.1.0:projectid_ec7e595a-63ee-46a1-a04a-901b11b649f8:nodeid_39467d89-b659-4914-9359-c40b1b6d1d6d:uuid_5ee5c655-450d-4711-a3ec-32ffe16bc580",
                    "progress": 0,
                },
                {
                    "job_id": "simcore/services/comp/sleeper:1.1.0:projectid_ec7e595a-63ee-46a1-a04a-901b11b649f8:nodeid_39467d89-b659-4914-9359-c40b1b6d1d6d:uuid_5ee5c655-450d-4711-a3ec-32ffe16bc580",
                    "progress": 1.0,
                },
            ]
        }


LogMessageStr: TypeAlias = str
LogLevelInt: TypeAlias = int


class TaskLogEvent(BaseTaskEvent):
    log: LogMessageStr
    log_level: LogLevelInt

    @staticmethod
    def topic_name() -> str:
        return "task_logs"

    @classmethod
    def from_dask_worker(cls, log: str, log_level: LogLevelInt) -> "TaskLogEvent":
        return cls(job_id=get_worker().get_current_task(), log=log, log_level=log_level)

    class Config(BaseTaskEvent.Config):
        schema_extra = {
            "examples": [
                {
                    "job_id": "simcore/services/comp/sleeper:1.1.0:projectid_ec7e595a-63ee-46a1-a04a-901b11b649f8:nodeid_39467d89-b659-4914-9359-c40b1b6d1d6d:uuid_5ee5c655-450d-4711-a3ec-32ffe16bc580",
                    "log": "some logs",
                    "log_level": logging.INFO,
                },
            ]
        }


DaskTaskEvents = type[Union[TaskLogEvent, TaskProgressEvent]]
