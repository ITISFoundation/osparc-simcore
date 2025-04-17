from datetime import datetime
from typing import Annotated, Any, NamedTuple

from pydantic import (
    BaseModel,
    BeforeValidator,
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


def _none_to_zero_float_pre_validator(value: Any):
    if value is None:
        return 0.0
    return value


class ComputationTaskRpcGet(BaseModel):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: Annotated[float, BeforeValidator(_none_to_zero_float_pre_validator)]
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None


class ComputationTaskRpcGetPage(NamedTuple):
    items: list[ComputationTaskRpcGet]
    total: PositiveInt
