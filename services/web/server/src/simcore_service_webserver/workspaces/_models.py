import logging

from models_library.basic_types import IDStr
from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_classes,
)
from models_library.rest_pagination import PageQueryParameters
from models_library.users import GroupID, UserID
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, Extra, Field
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY

_logger = logging.getLogger(__name__)


class WorkspacesRequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


class WorkspacesPathParams(StrictRequestParameters):
    workspace_id: WorkspaceID


WorkspacesListOrderQueryParams: type[
    RequestParameters
] = create_ordering_query_model_classes(
    ordering_fields={
        "modified_at",
        "name",
    },
    default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
    ordering_fields_api_to_column_map={"modified_at": "modified"},
)


class WorkspacesListQueryParams(
    PageQueryParameters,
    WorkspacesListOrderQueryParams,  # type: ignore[misc, valid-type]
):
    ...


class WorkspacesGroupsPathParams(BaseModel):
    workspace_id: WorkspaceID
    group_id: GroupID

    class Config:
        extra = Extra.forbid


class WorkspacesGroupsBodyParams(BaseModel):
    read: bool
    write: bool
    delete: bool

    class Config:
        extra = Extra.forbid
