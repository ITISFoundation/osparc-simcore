from datetime import datetime
from typing import Dict, Optional

from models_library.projects import NodeID, ProjectID, RunningState
from pydantic import BaseModel, Extra, Field, validator
from pydantic.types import PositiveInt
from simcore_postgres_database.models.comp_tasks import NodeClass, StateType


DB_TO_RUNNING_STATE = {
    StateType.FAILED: RunningState.FAILED,
    StateType.PENDING: RunningState.PENDING,
    StateType.SUCCESS: RunningState.SUCCESS,
    StateType.PUBLISHED: RunningState.PUBLISHED,
    StateType.NOT_STARTED: RunningState.NOT_STARTED,
    StateType.RUNNING: RunningState.STARTED,
    StateType.ABORTED: RunningState.ABORTED,
}


class CompTaskAtDB(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    job_id: Optional[str]
    node_schema: Dict = Field(..., alias="schema")
    inputs: Dict
    outputs: Dict
    image: Dict
    submit: datetime
    start: Optional[datetime]
    end: Optional[datetime]
    state: RunningState
    task_id: PositiveInt
    internal_id: PositiveInt
    node_class: NodeClass

    @validator("state", pre=True)
    @classmethod
    def secure_url(cls, v):
        if isinstance(v, StateType):
            return RunningState(DB_TO_RUNNING_STATE[StateType(v)])
        return v

    class Config:
        extra = Extra.forbid
        orm_mode = True
