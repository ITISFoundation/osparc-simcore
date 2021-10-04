from abc import ABC, abstractmethod
from typing import Optional

from distributed.worker import get_worker
from models_library.projects_state import RunningState
from pydantic import BaseModel, Extra


class TaskEvent(BaseModel, ABC):
    job_id: str
    msg: Optional[str]

    @staticmethod
    @abstractmethod
    def topic_name() -> str:
        raise NotImplementedError

    class Config:
        extra = Extra.forbid


class TaskStateEvent(TaskEvent):
    state: RunningState

    @staticmethod
    def topic_name() -> str:
        return "task_state"

    @classmethod
    def from_dask_worker(
        cls, state: RunningState, msg: Optional[str] = None
    ) -> "TaskStateEvent":
        return cls(job_id=get_worker().get_current_task(), state=state, msg=msg)

    class Config(TaskEvent.Config):
        schema_extra = {
            "examples": [
                {
                    "job_id": "simcore/services/comp/sleeper:1.1.0:projectid_ec7e595a-63ee-46a1-a04a-901b11b649f8:nodeid_39467d89-b659-4914-9359-c40b1b6d1d6d:uuid_5ee5c655-450d-4711-a3ec-32ffe16bc580",
                    "state": RunningState.STARTED.value,
                },
                {
                    "job_id": "simcore/services/comp/sleeper:1.1.0:projectid_ec7e595a-63ee-46a1-a04a-901b11b649f8:nodeid_39467d89-b659-4914-9359-c40b1b6d1d6d:uuid_5ee5c655-450d-4711-a3ec-32ffe16bc580",
                    "msg": "some unexpected error happened",
                    "state": RunningState.FAILED.value,
                },
            ]
        }
