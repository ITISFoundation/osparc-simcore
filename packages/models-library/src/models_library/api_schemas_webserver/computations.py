from datetime import datetime
from typing import Annotated, Any, NamedTuple

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
)

from ..api_schemas_directorv2.computations import (
    ComputationGet as _DirectorV2ComputationGet,
)
from ..projects import CommitID, ProjectID
from ..projects_nodes_io import NodeID
from ..projects_state import RunningState
from ._base import InputSchemaWithoutCamelCase, OutputSchemaWithoutCamelCase


class ComputationPathParams(BaseModel):
    project_id: ProjectID


class ComputationGet(_DirectorV2ComputationGet, OutputSchemaWithoutCamelCase):
    # NOTE: this is a copy of the same class in models_library.api_schemas_directorv2
    #       but it is used in a different context (webserver)
    #       and we need to add the `OutputSchema` mixin
    #       so that it can be used as a response model in FastAPI
    pass


class ComputationStart(InputSchemaWithoutCamelCase):
    force_restart: bool = False
    subgraph: Annotated[
        set[str], Field(default_factory=set, json_schema_extra={"default": []})
    ] = DEFAULT_FACTORY


class ComputationStarted(OutputSchemaWithoutCamelCase):
    pipeline_id: Annotated[
        ProjectID, Field(description="ID for created pipeline (=project identifier)")
    ]
    ref_ids: Annotated[
        list[CommitID],
        Field(
            default_factory=list,
            description="Checkpoints IDs for created pipeline",
            json_schema_extra={"default": []},
        ),
    ] = DEFAULT_FACTORY


class ComputationRunRestGet(BaseModel):
    project_uuid: ProjectID
    iteration: int
    state: RunningState
    info: dict[str, Any]
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class ComputationRunRestGetPage(NamedTuple):
    items: list[ComputationRunRestGet]
    total: PositiveInt


class ComputationTaskRestGet(BaseModel):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: float
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None


class ComputationTaskRestGetPage(NamedTuple):
    items: list[ComputationTaskRestGet]
    total: PositiveInt
