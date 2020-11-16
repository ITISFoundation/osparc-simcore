from typing import Dict, List

from models_library.projects import ProjectID, RunningState
from pydantic import BaseModel, validator


class CompPipelineAtDB(BaseModel):
    project_id: ProjectID
    dag_adjacency_list: Dict[str, List[str]]  # json serialization issue if using NodeID
    state: RunningState

    @validator("dag_adjacency_list", pre=True)
    @classmethod
    def auto_convert_dag(cls, v):
        # this enforcement is here because the serialization using json is not happy with non str Dict keys, also comparison gets funny if the lists are having sometimes UUIDs or str.
        # NOTE: this might not be necessary anymore once we have something fully defined
        return {str(key): [str(n) for n in value] for key, value in v.items()}

    class Config:
        orm_mode = True
