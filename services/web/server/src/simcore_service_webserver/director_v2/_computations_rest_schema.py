from models_library.basic_types import IDStr
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, create_ordering_query_model_class
from models_library.rest_pagination import PageQueryParameters
from pydantic import BaseModel, ConfigDict

### Computation Run


ComputationRunListOrderParams = create_ordering_query_model_class(
    ordering_fields={
        "submitted_at",
    },
    default=OrderBy(field=IDStr("submitted_at")),
    ordering_fields_api_to_column_map={"submitted_at": "created"},
)


class ComputationRunListQueryParams(
    PageQueryParameters,
    ComputationRunListOrderParams,
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
    ComputationTaskListOrderParams,
): ...
