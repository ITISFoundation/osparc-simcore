from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from models_library.projects import NodeID, ProjectID
from pydantic import BaseModel, Extra, Field
from pydantic.types import PositiveInt
from simcore_postgres_database.models.comp_tasks import NodeClass, StateType


class CompTaskAtDB(BaseModel):
    task_id: PositiveInt
    project_id: ProjectID
    node_id: NodeID
    job_id: Optional[str]
    internal_id: PositiveInt
    node_schema: Dict = Field(..., alias="schema")
    inputs: Dict
    outputs: Dict
    image: Dict
    submit: datetime
    start: Optional[datetime]
    end: Optional[datetime]
    node_class: NodeClass
    state: StateType

    class Config:
        orm_mode = True
        extra = Extra.forbid
