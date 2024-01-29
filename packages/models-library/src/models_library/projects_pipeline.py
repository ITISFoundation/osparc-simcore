import datetime
from uuid import UUID

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
    model_config = ConfigDict()
