from typing import Final

from models_library.wallets import WalletID
from pydantic import AnyHttpUrl, AnyUrl, BaseModel, Field, validator

from ..clusters import ClusterID
from ..projects import ProjectID
from ..projects_nodes_io import NodeID
from ..projects_pipeline import ComputationTask
from ..users import UserID

TEMPORARY_DEFAULT_WALLET_ID: Final[WalletID] = 43


class ComputationGet(ComputationTask):
    url: AnyHttpUrl = Field(
        ..., description="the link where to get the status of the task"
    )
    stop_url: AnyHttpUrl | None = Field(
        None, description="the link where to stop the task"
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
    )

    @validator("product_name", always=True)
    @classmethod
    def ensure_product_name_defined_if_computation_starts(cls, v, values):
        if "start_pipeline" in values and values["start_pipeline"] and v is None:
            msg = "product_name must be set if computation shall start!"
            raise ValueError(msg)
        return v

    @validator("use_on_demand_clusters", always=True)
    @classmethod
    def ensure_expected_options(cls, v, values):
        if v is True and ("cluster_id" in values and values["cluster_id"] is not None):
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
