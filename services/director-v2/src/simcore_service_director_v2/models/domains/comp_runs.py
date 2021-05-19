from datetime import datetime
from typing import Optional

from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pydantic import BaseModel, PositiveInt, validator
from simcore_postgres_database.models.comp_pipeline import StateType

from ...utils.db import DB_TO_RUNNING_STATE
from ..schemas.constants import UserID


class CompRunsAtDB(BaseModel):
    run_id: PositiveInt
    project_uuid: ProjectID
    user_id: UserID
    iteration: PositiveInt
    result: RunningState
    created: datetime
    modified: datetime
    start: Optional[datetime]
    end: Optional[datetime]

    @validator("result", pre=True)
    @classmethod
    def convert_result_if_needed(cls, v):
        if isinstance(v, StateType):
            return RunningState(DB_TO_RUNNING_STATE[StateType(v)])
        if isinstance(v, str):
            try:
                state_type = StateType(v)
                return RunningState(DB_TO_RUNNING_STATE[state_type])
            except ValueError:
                pass
        return v

    class Config:
        orm_mode = True
