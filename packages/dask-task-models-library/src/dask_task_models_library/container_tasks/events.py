from typing import Optional

from distributed.worker import get_worker
from models_library.projects_state import RunningState
from pydantic import BaseModel


class TaskStateEvent(BaseModel):
    job_id: str
    state: RunningState
    msg: Optional[str]

    @staticmethod
    def topic_name() -> str:
        return "task_state"

    @classmethod
    def from_dask_worker(cls, state: RunningState, msg: Optional[str] = None):
        return cls(job_id=get_worker().get_current_task(), state=state, msg=msg)
