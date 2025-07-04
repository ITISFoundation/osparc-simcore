from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from ..api_schemas_directorv2.computations import (
    ComputationGet as _DirectorV2ComputationGet,
)
from ..basic_types import IDStr
from ..computations import CollectionRunID
from ..projects import CommitID, ProjectID
from ..projects_nodes_io import NodeID
from ..projects_state import RunningState
from ..rest_ordering import OrderBy, create_ordering_query_model_class
from ..rest_pagination import PageQueryParameters
from ..utils.common_validators import null_or_none_str_to_none_validator
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


class ComputationRunIterationsLatestListQueryParams(ComputationRunListQueryParams):
    filter_only_running: bool = Field(
        default=False,
        description="If true, only running computations are returned",
    )


class ComputationRunIterationsListQueryParams(ComputationRunListQueryParams):
    include_children: bool = Field(
        default=False,
        description="If true, all computational runs of the project and its children are returned (Currently supported only for root projects)",
    )


class ComputationRunRestGet(OutputSchema):
    project_uuid: ProjectID
    iteration: int
    state: RunningState
    info: dict[str, Any]
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    root_project_name: str
    project_custom_metadata: dict[str, Any]


class ComputationRunPathParams(BaseModel):
    project_id: ProjectID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


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
):
    include_children: bool = Field(
        default=False,
        description="If true, all tasks of the project and its children are returned (Currently supported only for root projects)",
    )


class ComputationTaskRestGet(OutputSchema):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: float
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
    log_download_link: AnyUrl | None
    node_name: str
    osparc_credits: Decimal | None


### Computation Collection Run


class ComputationCollectionRunListQueryParams(
    PageQueryParameters,
):
    filter_only_running: Annotated[
        bool, Field(description="If true, only running collection runs are returned")
    ] = False

    filter_by_root_project_id: ProjectID | None = None

    _null_or_none_to_none = field_validator("filter_by_root_project_id", mode="before")(
        null_or_none_str_to_none_validator
    )


class ComputationCollectionRunRestGet(OutputSchema):
    collection_run_id: CollectionRunID
    project_ids: list[str]
    state: RunningState
    info: dict[str, Any]
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    name: str


class ComputationCollectionRunPathParams(BaseModel):
    collection_run_id: CollectionRunID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ComputationCollectionRunTaskListQueryParams(
    PageQueryParameters,
): ...


class ComputationCollectionRunTaskRestGet(OutputSchema):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: float
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
    log_download_link: AnyUrl | None
    osparc_credits: Decimal | None
    name: str
