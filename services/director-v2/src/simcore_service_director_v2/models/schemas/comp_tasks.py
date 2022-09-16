from typing import Optional

from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_pipeline import ComputationTask
from models_library.users import UserID
from pydantic import AnyHttpUrl, AnyUrl, BaseModel, Field


class ComputationGet(ComputationTask):
    url: AnyHttpUrl = Field(
        ..., description="the link where to get the status of the task"
    )
    stop_url: Optional[AnyHttpUrl] = Field(
        None, description="the link where to stop the task"
    )


class ComputationCreate(BaseModel):
    user_id: UserID
    project_id: ProjectID
    product_name: str
    start_pipeline: Optional[bool] = Field(
        default=False,
        description="if True the computation pipeline will start right away",
    )
    subgraph: Optional[list[NodeID]] = Field(
        default=None,
        description="An optional set of nodes that must be executed, if empty the whole pipeline is executed",
    )
    force_restart: Optional[bool] = Field(
        default=False, description="if True will force re-running all dependent nodes"
    )
    cluster_id: Optional[ClusterID] = Field(
        default=None,
        description="the computation shall use the cluster described by its id, 0 is the default cluster",
    )


class ComputationStop(BaseModel):
    user_id: UserID


class ComputationDelete(ComputationStop):
    force: Optional[bool] = Field(
        False,
        description="if True then the pipeline will be removed even if it is running",
    )


class TaskLogFileGet(BaseModel):
    task_id: NodeID
    download_link: Optional[AnyUrl] = Field(
        None, description="Presigned link for log file or None if still not available"
    )
