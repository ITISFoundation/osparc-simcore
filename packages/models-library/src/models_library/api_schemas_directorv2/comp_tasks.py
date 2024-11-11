from typing import Any, TypeAlias

from models_library.basic_types import IDStr
from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)

from ..clusters import ClusterID
from ..projects import ProjectID
from ..projects_nodes_io import NodeID
from ..projects_pipeline import ComputationTask
from ..users import UserID
from ..wallets import WalletInfo


class ComputationGet(ComputationTask):
    url: AnyHttpUrl = Field(
        ..., description="the link where to get the status of the task"
    )
    stop_url: AnyHttpUrl | None = Field(
        None, description="the link where to stop the task"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                x | {"url": "http://url.local"}  # type:ignore[operator]
                for x in ComputationTask.model_config[  # type:ignore[index,union-attr]
                    "json_schema_extra"
                ]["examples"]
            ]
        }
    )


class ComputationCreate(BaseModel):
    user_id: UserID
    project_id: ProjectID
    start_pipeline: bool | None = Field(
        default=False,
        description="if True the computation pipeline will start right away",
    )
    product_name: str
    subgraph: list[NodeID] | None = Field(
        default=None,
        description="An optional set of nodes that must be executed, if empty the whole pipeline is executed",
    )
    force_restart: bool | None = Field(
        default=False, description="if True will force re-running all dependent nodes"
    )
    cluster_id: ClusterID | None = Field(
        default=None,
        description="the computation shall use the cluster described by its id, 0 is the default cluster",
    )
    simcore_user_agent: str = ""
    use_on_demand_clusters: bool = Field(
        default=False,
        description="if True, a cluster will be created as necessary (wallet_id cannot be None, and cluster_id must be None)",
        validate_default=True,
    )
    wallet_info: WalletInfo | None = Field(
        default=None,
        description="contains information about the wallet used to bill the running service",
    )

    @field_validator("product_name")
    @classmethod
    def _ensure_product_name_defined_if_computation_starts(
        cls, v, info: ValidationInfo
    ):
        if info.data.get("start_pipeline") and v is None:
            msg = "product_name must be set if computation shall start!"
            raise ValueError(msg)
        return v

    @field_validator("use_on_demand_clusters")
    @classmethod
    def _ensure_expected_options(cls, v, info: ValidationInfo):
        if v and info.data.get("cluster_id") is not None:
            msg = "cluster_id cannot be set if use_on_demand_clusters is set"
            raise ValueError(msg)
        return v


class ComputationStop(BaseModel):
    user_id: UserID


class ComputationDelete(ComputationStop):
    force: bool | None = Field(
        default=False,
        description="if True then the pipeline will be removed even if it is running",
    )


class TaskLogFileGet(BaseModel):
    task_id: NodeID
    download_link: AnyUrl | None = Field(
        None, description="Presigned link for log file or None if still not available"
    )


class TasksSelection(BaseModel):
    nodes_ids: list[NodeID]


OutputName: TypeAlias = IDStr


class TasksOutputs(BaseModel):
    nodes_outputs: dict[NodeID, dict[OutputName, Any]]
