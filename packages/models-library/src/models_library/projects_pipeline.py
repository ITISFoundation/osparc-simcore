import datetime
from uuid import UUID

import arrow
from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from .clusters import ClusterID
from .projects_nodes import NodeState
from .projects_nodes_io import NodeID
from .projects_state import RunningState


class PipelineDetails(BaseModel):
    adjacency_list: dict[NodeID, list[NodeID]] = Field(
        ...,
        description="The adjacency list of the current pipeline in terms of {NodeID: [successor NodeID]}",
    )
    progress: float | None = Field(
        ...,
        ge=0,
        le=1.0,
        description="the progress of the pipeline (None if there are no computational tasks)",
    )
    node_states: dict[NodeID, NodeState] = Field(
        ..., description="The states of each of the computational nodes in the pipeline"
    )


TaskID = UUID


class ComputationTask(BaseModel):
    id: TaskID = Field(..., description="the id of the computation task")
    state: RunningState = Field(..., description="the state of the computational task")
    result: str | None = Field(None, description="the result of the computational task")
    pipeline_details: PipelineDetails = Field(
        ..., description="the details of the generated pipeline"
    )
    iteration: PositiveInt | None = Field(
        ...,
        description="the iteration id of the computation task (none if no task ran yet)",
    )
    cluster_id: ClusterID | None = Field(
        ...,
        description="the cluster on which the computaional task runs/ran (none if no task ran yet)",
    )
    started: datetime.datetime | None = Field(
        ...,
        description="the timestamp when the computation was started or None if not started yet",
    )
    stopped: datetime.datetime | None = Field(
        ...,
        description="the timestamp when the computation was stopped or None if not started nor stopped yet",
    )
    submitted: datetime.datetime | None = Field(
        ...,
        description="task last modification timestamp or None if the there is no task",
    )

    model_config = ConfigDict(
        json_schema_extra={
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
                                "progress": 0.0,
                            },
                            "19a40c7b-0a40-458a-92df-c77a5df7c886": {
                                "modified": False,
                                "dependencies": [
                                    "2fb4808a-e403-4a46-b52c-892560d27862"
                                ],
                                "progress": 0.0,
                            },
                        },
                        "progress": 0.0,
                    },
                    "iteration": None,
                    "cluster_id": None,
                    "started": arrow.utcnow().shift(minutes=-50).datetime,  # type: ignore[dict-item]
                    "stopped": None,
                    "submitted": arrow.utcnow().shift(hours=-1).datetime,  # type: ignore[dict-item]
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
                                "progress": 1.0,
                            },
                            "19a40c7b-0a40-458a-92df-c77a5df7c886": {
                                "modified": False,
                                "dependencies": [
                                    "2fb4808a-e403-4a46-b52c-892560d27862"
                                ],
                                "progress": 1.0,
                            },
                        },
                        "progress": 1.0,
                    },
                    "iteration": 2,
                    "cluster_id": 0,
                    "started": arrow.utcnow().shift(minutes=-50).datetime,  # type: ignore[dict-item]
                    "stopped": arrow.utcnow().shift(minutes=-20).datetime,  # type: ignore[dict-item]
                    "submitted": arrow.utcnow().shift(hours=-1).datetime,  # type: ignore[dict-item]
                },
            ]
        }
    )
