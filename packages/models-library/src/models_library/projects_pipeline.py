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

    class Config:
        schema_extra = {
            "example": {
                "id": "42838344-03de-4ce2-8d93-589a5dcdfd05",
                "state": "PUBLISHED",
                "pipeline_details": {
                    "adjacency_list": {
                        "2fb4808a-e403-4a46-b52c-892560d27862": [],
                        "19a40c7b-0a40-458a-92df-c77a5df7c886": [
                            "2fb4808a-e403-4a46-b52c-892560d27862"
                        ],
                    },
                    "node_states": {
                        "2fb4808a-e403-4a46-b52c-892560d27862": {
                            "modified": True,
                            "dependencies": [],
                        },
                        "19a40c7b-0a40-458a-92df-c77a5df7c886": {
                            "modified": False,
                            "dependencies": ["2fb4808a-e403-4a46-b52c-892560d27862"],
                        },
                    },
                },
            }
        }
