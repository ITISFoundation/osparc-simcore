from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, PositiveInt

from .clusters import ClusterID
from .projects_nodes import NodeID, NodeState
from .projects_state import RunningState


class PipelineDetails(BaseModel):
    adjacency_list: Dict[NodeID, List[NodeID]] = Field(
        ...,
        description="The adjacency list of the current pipeline in terms of {NodeID: [successor NodeID]}",
    )
    node_states: Dict[NodeID, NodeState] = Field(
        ..., description="The states of each of the computational nodes in the pipeline"
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
    iteration: Optional[PositiveInt] = Field(
        ...,
        description="the iteration id of the computation task (none if no task ran yet)",
    )
    cluster_id: Optional[ClusterID] = Field(
        ...,
        description="the cluster on which the computaional task runs/ran (none if no task ran yet)",
    )

    class Config:
        schema_extra = {
            "examples": [
                {
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
                                "dependencies": [
                                    "2fb4808a-e403-4a46-b52c-892560d27862"
                                ],
                            },
                        },
                    },
                    "iteration": None,
                    "cluster_id": None,
                },
                {
                    "id": "f81d7994-9ccc-4c95-8c32-aa70d6bbb1b0",
                    "state": "SUCCESS",
                    "pipeline_details": {
                        "adjacency_list": {
                            "2fb4808a-e403-4a46-b52c-892560d27862": [],
                            "19a40c7b-0a40-458a-92df-c77a5df7c886": [
                                "2fb4808a-e403-4a46-b52c-892560d27862"
                            ],
                        },
                        "node_states": {
                            "2fb4808a-e403-4a46-b52c-892560d27862": {
                                "modified": False,
                                "dependencies": [],
                            },
                            "19a40c7b-0a40-458a-92df-c77a5df7c886": {
                                "modified": False,
                                "dependencies": [
                                    "2fb4808a-e403-4a46-b52c-892560d27862"
                                ],
                            },
                        },
                    },
                    "iteration": 2,
                    "cluster_id": 0,
                },
            ]
        }
