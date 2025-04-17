from models_library.basic_types import IDStr
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, create_ordering_query_model_class
from models_library.rest_pagination import PageQueryParameters
from pydantic import BaseModel, ConfigDict

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
