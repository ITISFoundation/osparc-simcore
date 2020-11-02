from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from models_library.constants import VERSION_RE
from models_library.projects import NodeID, ProjectID, RunningState
from models_library.services import KEY_RE
from pydantic import BaseModel, Extra, Field, HttpUrl, constr, validator
from pydantic.types import PositiveInt
from simcore_postgres_database.models.comp_tasks import NodeClass, StateType

TaskID = UUID


class ComputationTask(BaseModel):
    id: TaskID = Field(..., description="the id of the computation task")
    state: RunningState = Field(..., description="the state of the computational task")
    result: Optional[str] = Field(
        None, description="the result of the computational task"
    )


class ComputationTaskOut(ComputationTask):
    url: HttpUrl = Field(
        ..., description="the link where to get the status of the task"
    )


DB_TO_RUNNING_STATE = {
    StateType.FAILED: RunningState.FAILED,
    StateType.PENDING: RunningState.PENDING,
    StateType.SUCCESS: RunningState.SUCCESS,
    StateType.PUBLISHED: RunningState.PUBLISHED,
    StateType.NOT_STARTED: RunningState.NOT_STARTED,
    StateType.RUNNING: RunningState.STARTED,
    StateType.ABORTED: RunningState.ABORTED,
}


class Image(BaseModel):
    name: constr(regex=KEY_RE)
    tag: constr(regex=VERSION_RE)
    requires_gpu: bool
    requires_mpi: bool


class CompTaskAtDB(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    job_id: Optional[str] = Field(None, description="The celery job ID")
    node_schema: Dict = Field(
        ..., description="the schema for inputs/outputs", alias="schema"
    )
    inputs: Dict = Field(..., description="the inputs payload")
    outputs: Dict = Field(..., description="the outputs payload")
    image: Image
    submit: datetime
    start: Optional[datetime]
    end: Optional[datetime]
    state: RunningState
    task_id: PositiveInt
    internal_id: PositiveInt
    node_class: NodeClass

    @validator("state", pre=True)
    @classmethod
    def convert_state_if_needed(cls, v):
        if isinstance(v, StateType):
            return RunningState(DB_TO_RUNNING_STATE[StateType(v)])
        return v

    class Config:
        extra = Extra.forbid
        orm_mode = True
