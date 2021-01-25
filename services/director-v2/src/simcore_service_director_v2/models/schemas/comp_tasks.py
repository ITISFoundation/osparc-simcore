from enum import Enum, unique
from typing import Dict, List, Optional
from uuid import UUID

from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_state import RunningState
from pydantic import AnyHttpUrl, BaseModel, Field

from ..schemas.constants import UserID

TaskID = UUID


@unique
class NodeIOState(str, Enum):
    OK = "OK"
    OUTDATED = "OUTDATED"


@unique
class NodeRunnableState(str, Enum):
    WAITING_FOR_DEPENDENCIES = "WAITING_FOR_DEPENDENCIES"
    READY = "READY"


class NodeState(BaseModel):
    io_state: NodeIOState = Field(
        ..., description="represents the state of the inputs outputs"
    )
    runnable_state: NodeRunnableState = Field(
        ..., description="represent the runnable state of the node"
    )


class PipelineDetails(BaseModel):
    adjacency_list: Dict[NodeID, List[NodeID]] = Field(
        ..., description="The adjacency list in terms of {NodeID: [successor NodeID]}"
    )
    node_states: Dict[NodeID, NodeState] = Field(
        ..., description="The states of each of the pipeline node"
    )


class ComputationTask(BaseModel):
    id: TaskID = Field(..., description="the id of the computation task")
    state: RunningState = Field(..., description="the state of the computational task")
    result: Optional[str] = Field(
        None, description="the result of the computational task"
    )
    pipeline_details: PipelineDetails = Field(
        ..., description="the details of the generated pipeline"
    )


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
