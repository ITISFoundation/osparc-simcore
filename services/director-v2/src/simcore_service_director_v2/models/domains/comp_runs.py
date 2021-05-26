from datetime import datetime
from typing import Optional

from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pydantic import BaseModel, PositiveInt, validator
from simcore_postgres_database.models.comp_pipeline import StateType

from ...utils.db import DB_TO_RUNNING_STATE
from ..schemas.constants import UserID

from contextlib import suppress


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
    def convert_result_from_state_type_enum_if_needed(cls, v):
        if isinstance(v, str):
            # try to convert to a StateType, if it fails the validations will continue
            # and pydantic will try to convert it to a RunninState later on
            with suppress(ValueError):
                v = StateType(v)
        if isinstance(v, StateType):
            return RunningState(DB_TO_RUNNING_STATE[StateType(v)])
        return v

    class Config:
        orm_mode = True
