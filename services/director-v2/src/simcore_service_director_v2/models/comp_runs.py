import datetime
from contextlib import suppress
from typing import Any, ClassVar, TypedDict

from models_library.clusters import DEFAULT_CLUSTER_ID, ClusterID
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import BaseModel, Field, PositiveInt, validator
from simcore_postgres_database.models.comp_pipeline import StateType

from ..utils.db import DB_TO_RUNNING_STATE


class MetadataDict(TypedDict):
    node_id_names_map: dict[NodeID, str]
    project_name: str
    product_name: str
    simcore_user_agent: str
    user_email: str
    wallet_id: int
    wallet_name: str


class CompRunsAtDB(BaseModel):
    run_id: PositiveInt
    project_uuid: ProjectID
    user_id: UserID
    cluster_id: ClusterID | None
    iteration: PositiveInt
    result: RunningState
    created: datetime.datetime
    modified: datetime.datetime
    started: datetime.datetime | None
    ended: datetime.datetime | None
    metadata: MetadataDict = Field(default_factory=dict)

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

    @validator("cluster_id", pre=True)
    @classmethod
    def convert_null_to_default_cluster_id(cls, v):
        if v is None:
            v = DEFAULT_CLUSTER_ID
        return v

    @validator("metadata", pre=True)
    @classmethod
    def convert_null_to_empty_metadata(cls, v):
        if v is None:
            v = MetadataDict()
        return v

    @validator("created", "modified", "started", "ended")
    @classmethod
    def ensure_utc(cls, v: datetime.datetime | None) -> datetime.datetime | None:
        if v is not None and v.tzinfo is None:
            v = v.replace(tzinfo=datetime.timezone.utc)
        return v

    class Config:
        orm_mode = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # DB model
                {
                    "run_id": 432,
                    "project_uuid": "65fee9d2-e030-452c-a29c-45d288577ca5",
                    "user_id": 132,
                    "cluster_id": 0,
                    "iteration": 42,
                    "result": "NOT_STARTED",
                    "created": "2021-03-01 13:07:34.19161",
                    "modified": "2021-03-01 13:07:34.19161",
                },
                {
                    "run_id": 43243,
                    "project_uuid": "65fee9d2-e030-452c-a29c-45d288577ca5",
                    "user_id": 132,
                    "cluster_id": 123,
                    "iteration": 12,
                    "result": "SUCCESS",
                    "created": "2021-03-01 13:07:34.19161",
                    "modified": "2021-03-01 13:07:34.19161",
                    "started": "2021-03-01 8:07:34.19161",
                    "ended": "2021-03-01 13:07:34.10",
                    "metadata": {
                        "product_name": "osparc",
                        "some-other-metadata-which-is-an-array": [1, 3, 4],
                    },
                },
            ]
        }
