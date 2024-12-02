import logging
from typing import Annotated

from models_library.basic_types import IDStr
from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.rest_filters import Filters, FiltersQueryParameters
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_class,
)
from models_library.rest_pagination import PageQueryParameters
from models_library.trash import RemoveQueryParams
from models_library.users import GroupID, UserID
from models_library.utils.common_validators import empty_str_to_none_pre_validator
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY

_logger = logging.getLogger(__name__)


class WorkspacesRequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


class WorkspacesPathParams(StrictRequestParameters):
    workspace_id: WorkspaceID


_WorkspacesListOrderQueryParams: type[
    RequestParameters
] = create_ordering_query_model_class(
    ordering_fields={
        "modified_at",
        "name",
    },
    default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
    ordering_fields_api_to_column_map={"modified_at": "modified"},
)


class WorkspacesFilters(Filters):
    trashed: bool | None = Field(
        default=False,
        description="Set to true to list trashed, false to list non-trashed (default), None to list all",
    )
    text: Annotated[
        str | None, BeforeValidator(empty_str_to_none_pre_validator)
    ] = Field(
        default=None,
        description="Multi column full text search",
        max_length=100,
        examples=["My Workspace"],
    )


class WorkspacesListQueryParams(
    PageQueryParameters,
    FiltersQueryParameters[WorkspacesFilters],
    _WorkspacesListOrderQueryParams,  # type: ignore[misc, valid-type]
):
    ...


class WorkspacesGroupsPathParams(BaseModel):
    workspace_id: WorkspaceID
    group_id: GroupID
    model_config = ConfigDict(extra="forbid")


class WorkspacesGroupsBodyParams(BaseModel):
    read: bool
    write: bool
    delete: bool
    model_config = ConfigDict(extra="forbid")


class WorkspaceTrashQueryParams(RemoveQueryParams):
    ...
