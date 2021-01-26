from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .projects_nodes import NodeID, NodeState
from .projects_state import RunningState


class PipelineDetails(BaseModel):
    adjacency_list: Dict[NodeID, List[NodeID]] = Field(
        ..., description="The adjacency list in terms of {NodeID: [successor NodeID]}"
    )
    node_states: Dict[NodeID, NodeState] = Field(
        ..., description="The states of each of the pipeline node"
    )


TaskID = UUID


class ComputationTask(BaseModel):
    id: TaskID = Field(..., description="the id of the computation task")
    state: RunningState = Field(..., description="the state of the computational task")
    result: Optional[str] = Field(
        None, description="the result of the computational task"
    )
    pipeline_details: PipelineDetails = Field(
        ..., description="the details of the generated pipeline"
    )
