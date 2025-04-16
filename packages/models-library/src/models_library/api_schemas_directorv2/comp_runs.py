from datetime import datetime
from typing import Any, NamedTuple

from pydantic import (
    BaseModel,
    PositiveInt,
)

from ..projects import ProjectID
from ..projects_nodes_io import NodeID
from ..projects_state import RunningState


class ComputationRunRpcGet(BaseModel):
    project_uuid: ProjectID
    iteration: int
    state: RunningState
    info: dict[str, Any]
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class ComputationRunRpcGetPage(NamedTuple):
    items: list[ComputationRunRpcGet]
    total: PositiveInt


class ComputationTaskRpcGet(BaseModel):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: float
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None


class ComputationTaskRpcGetPage(NamedTuple):
    items: list[ComputationTaskRpcGet]
    total: PositiveInt
