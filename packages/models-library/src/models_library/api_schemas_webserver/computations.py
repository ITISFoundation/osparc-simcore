from datetime import datetime
from typing import Annotated, Any

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from ..api_schemas_directorv2.computations import (
    ComputationGet as _DirectorV2ComputationGet,
)
from ..basic_types import IDStr
from ..projects import CommitID, ProjectID
from ..projects_nodes_io import NodeID
from ..projects_state import RunningState
from ..rest_ordering import OrderBy, create_ordering_query_model_class
from ..rest_pagination import PageQueryParameters
from ._base import (
    InputSchemaWithoutCamelCase,
    OutputSchema,
    OutputSchemaWithoutCamelCase,
)


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


### Computation Run


ComputationRunListOrderParams = create_ordering_query_model_class(
    ordering_fields={
        "submitted_at",
        "started_at",
        "ended_at",
        "state",
    },
    default=OrderBy(field=IDStr("submitted_at")),
    ordering_fields_api_to_column_map={
        "submitted_at": "created",
        "started_at": "started",
        "ended_at": "ended",
    },
)


class ComputationRunListQueryParams(
    PageQueryParameters,
    ComputationRunListOrderParams,  # type: ignore[misc, valid-type]
): ...


class ComputationRunRestGet(OutputSchema):
    project_uuid: ProjectID
    iteration: int
    state: RunningState
    info: dict[str, Any]
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


### Computation Task


class ComputationTaskPathParams(BaseModel):
    project_id: ProjectID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


ComputationTaskListOrderParams = create_ordering_query_model_class(
    ordering_fields={
        "started_at",
    },
    default=OrderBy(field=IDStr("started_at")),
    ordering_fields_api_to_column_map={"started_at": "start"},
)


class ComputationTaskListQueryParams(
    PageQueryParameters,
    ComputationTaskListOrderParams,  # type: ignore[misc, valid-type]
): ...


class ComputationTaskRestGet(OutputSchema):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: float
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
