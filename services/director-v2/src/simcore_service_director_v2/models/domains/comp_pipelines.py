from contextlib import suppress
from typing import Dict, List

import networkx as nx
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pydantic import BaseModel, validator
from simcore_postgres_database.models.comp_pipeline import StateType

from ...utils.db import DB_TO_RUNNING_STATE


class CompPipelineAtDB(BaseModel):
    project_id: ProjectID
    dag_adjacency_list: Dict[str, List[str]]  # json serialization issue if using NodeID
    state: RunningState

    @validator("state", pre=True)
    @classmethod
    def convert_state_from_state_type_enum_if_needed(cls, v):
        if isinstance(v, str):
            # try to convert to a StateType, if it fails the validations will continue
            # and pydantic will try to convert it to a RunninState later on
            with suppress(ValueError):
                v = StateType(v)
        if isinstance(v, StateType):
            return RunningState(DB_TO_RUNNING_STATE[StateType(v)])
        return v

    @validator("dag_adjacency_list", pre=True)
    @classmethod
    def auto_convert_dag(cls, v):
        # this enforcement is here because the serialization using json is not happy with non str Dict keys, also comparison gets funny if the lists are having sometimes UUIDs or str.
        # NOTE: this might not be necessary anymore once we have something fully defined
        return {str(key): [str(n) for n in value] for key, value in v.items()}

    def get_graph(self) -> nx.DiGraph:
        return nx.from_dict_of_lists(self.dag_adjacency_list, create_using=nx.DiGraph)

    class Config:
        orm_mode = True

        schema_extra = {
            "examples": [
                # DB model
                {
                    "project_id": "65fee9d2-e030-452c-a29c-45d288577ca5",
                    "dag_adjacency_list": {
                        "539531c4-afb9-4ca8-bda3-06ad3d7bc339": [
                            "f98e20e5-b235-43ed-a63d-15b71bc7c762"
                        ],
                        "f98e20e5-b235-43ed-a63d-15b71bc7c762": [],
                        "5332fcde-b043-41f5-8786-a3a359b110ad": [],
                    },
                    "state": "NOT_STARTED",
                }
            ]
        }
