from typing import List, Optional

from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_pipeline import ComputationTask
from pydantic import AnyHttpUrl, BaseModel, Field

from ..schemas.constants import UserID


class ComputationTaskOut(ComputationTask):
    url: AnyHttpUrl = Field(
        ..., description="the link where to get the status of the task"
    )
    stop_url: Optional[AnyHttpUrl] = Field(
        None, description="the link where to stop the task"
    )


class ComputationTaskCreate(BaseModel):
    user_id: UserID
    project_id: ProjectID
    start_pipeline: Optional[bool] = Field(
        False, description="if True the computation pipeline will start right away"
    )
    subgraph: Optional[List[NodeID]] = Field(
        None,
        description="An optional set of nodes that must be executed, if empty the whole pipeline is executed",
    )
    force_restart: Optional[bool] = Field(
        False, description="if True will force re-running all dependent nodes"
    )


class ComputationTaskStop(BaseModel):
    user_id: UserID


class ComputationTaskDelete(ComputationTaskStop):
    force: Optional[bool] = Field(
        False,
        description="if True then the pipeline will be removed even if it is running",
    )
