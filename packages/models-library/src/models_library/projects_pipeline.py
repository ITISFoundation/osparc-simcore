from typing import Dict, List

from pydantic import BaseModel, Field

from .projects_nodes import NodeID, NodeState


class PipelineDetails(BaseModel):
    adjacency_list: Dict[NodeID, List[NodeID]] = Field(
        ..., description="The adjacency list in terms of {NodeID: [successor NodeID]}"
    )
    node_states: Dict[NodeID, NodeState] = Field(
        ..., description="The states of each of the pipeline node"
    )
