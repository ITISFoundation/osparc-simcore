import datetime
from contextlib import suppress
from typing import TypeAlias

from models_library.clusters import DEFAULT_CLUSTER_ID, ClusterID
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import BaseModel, ConfigDict, PositiveInt, field_validator
from simcore_postgres_database.models.comp_pipeline import StateType
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

from ..utils.db import DB_TO_RUNNING_STATE


class ProjectMetadataDict(TypedDict, total=False):
    parent_node_id: NodeID
    parent_node_name: str
    parent_project_id: ProjectID
    parent_project_name: str
    root_parent_project_id: ProjectID
    root_parent_project_name: str
    root_parent_node_id: NodeID
    root_parent_node_name: str


class RunMetadataDict(TypedDict, total=False):
    node_id_names_map: dict[NodeID, str]
    project_name: str
    product_name: str
    simcore_user_agent: str
    user_email: str
    wallet_id: int | None
    wallet_name: str | None
    project_metadata: ProjectMetadataDict


Iteration: TypeAlias = PositiveInt


class CompRunsAtDB(BaseModel):
    run_id: PositiveInt
    project_uuid: ProjectID
    user_id: UserID
    cluster_id: ClusterID | None
    iteration: Iteration
    result: RunningState
    created: datetime.datetime
    modified: datetime.datetime
    started: datetime.datetime | None
    ended: datetime.datetime | None
    cancelled: datetime.datetime | None
    metadata: RunMetadataDict = RunMetadataDict()
    use_on_demand_clusters: bool
    scheduled: datetime.datetime | None
    processed: datetime.datetime | None

    @field_validator("result", mode="before")
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

    @field_validator("cluster_id", mode="before")
    @classmethod
    def convert_null_to_default_cluster_id(cls, v):
        if v is None:
            v = DEFAULT_CLUSTER_ID
        return v

    @field_validator("created", "modified", "started", "ended")
    @classmethod
    def ensure_utc(cls, v: datetime.datetime | None) -> datetime.datetime | None:
        if v is not None and v.tzinfo is None:
            v = v.replace(tzinfo=datetime.UTC)
        return v

    @field_validator("metadata", mode="before")
    @classmethod
    def convert_null_to_empty_metadata(cls, v):
        if v is None:
            v = RunMetadataDict()
        return v

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                # DB model
                {
                    "run_id": 432,
                    "project_uuid": "65fee9d2-e030-452c-a29c-45d288577ca5",
                    "user_id": 132,
                    "cluster_id": 0,
                    "iteration": 42,
                    "result": "UNKNOWN",
                    "started": None,
                    "ended": None,
                    "created": "2021-03-01T13:07:34.191610",
                    "modified": "2021-03-01T13:07:34.191610",
                    "cancelled": None,
                    "use_on_demand_clusters": False,
                    "scheduled": None,
                    "processed": None,
                },
                {
                    "run_id": 432,
                    "project_uuid": "65fee9d2-e030-452c-a29c-45d288577ca5",
                    "user_id": 132,
                    "cluster_id": None,  # this default to DEFAULT_CLUSTER_ID
                    "iteration": 42,
                    "result": "NOT_STARTED",
                    "started": None,
                    "ended": None,
                    "created": "2021-03-01T13:07:34.191610",
                    "modified": "2021-03-01T13:07:34.191610",
                    "cancelled": None,
                    "use_on_demand_clusters": False,
                    "scheduled": None,
                    "processed": None,
                },
                {
                    "run_id": 43243,
                    "project_uuid": "65fee9d2-e030-452c-a29c-45d288577ca5",
                    "user_id": 132,
                    "cluster_id": 123,
                    "iteration": 12,
                    "result": "SUCCESS",
                    "created": "2021-03-01T13:07:34.191610",
                    "modified": "2021-03-01T13:07:34.191610",
                    "started": "2021-03-01T08:07:34.191610",
                    "ended": "2021-03-01T13:07:34.10",
                    "cancelled": None,
                    "metadata": {
                        "node_id_names_map": {},
                        "product_name": "osparc",
                        "project_name": "my awesome project",
                        "simcore_user_agent": "undefined",
                        "some-other-metadata-which-is-an-array": [1, 3, 4],
                    },
                    "use_on_demand_clusters": False,
                    "scheduled": None,
                    "processed": None,
                },
                {
                    "run_id": 43243,
                    "project_uuid": "65fee9d2-e030-452c-a29c-45d288577ca5",
                    "user_id": 132,
                    "cluster_id": 123,
                    "iteration": 12,
                    "result": "SUCCESS",
                    "created": "2021-03-01T13:07:34.191610",
                    "modified": "2021-03-01T13:07:34.191610",
                    "started": "2021-03-01T08:07:34.191610",
                    "ended": "2021-03-01T13:07:34.10",
                    "cancelled": None,
                    "metadata": None,
                    "use_on_demand_clusters": False,
                    "scheduled": None,
                    "processed": None,
                },
            ]
        },
    )
