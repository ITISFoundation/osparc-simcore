import logging

from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.rest_filters import Filters, FiltersQueryParameters
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_classes,
)
from models_library.rest_pagination import PageQueryParameters
from models_library.users import UserID
from models_library.utils.common_validators import (
    empty_str_to_none_pre_validator,
    null_or_none_str_to_none_validator,
)
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, Extra, Field, validator
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY

_logger = logging.getLogger(__name__)


class FoldersRequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


class FoldersPathParams(StrictRequestParameters):
    folder_id: FolderID


class FolderFilters(Filters):
    trashed: bool | None = Field(
        default=False,
        description="Set to true to list trashed, false to list non-trashed (default), None to list all",
    )


_FolderOrderQueryParams: type[RequestParameters] = create_ordering_query_model_classes(
    ordering_fields={
        "modified_at",
        "name",
    },
    default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
    ordering_fields_api_to_column_map={"modified_at": "modified"},
)


class FoldersListQueryParams(
    PageQueryParameters, _FolderOrderQueryParams, FiltersQueryParameters[FolderFilters]  # type: ignore[misc, valid-type]
):
    folder_id: FolderID | None = Field(
        default=None,
        description="List the subfolders of this folder. By default, list the subfolders of the root directory (Folder ID is None).",
    )
    workspace_id: WorkspaceID | None = Field(
        default=None,
        description="List folders in specific workspace. By default, list in the user private workspace",
    )

    class Config:
        extra = Extra.forbid

    # validators
    _null_or_none_str_to_none_validator = validator(
        "folder_id", allow_reuse=True, pre=True
    )(null_or_none_str_to_none_validator)

    _null_or_none_str_to_none_validator2 = validator(
        "workspace_id", allow_reuse=True, pre=True
    )(null_or_none_str_to_none_validator)


class FolderSearchQueryParams(
    PageQueryParameters, _FolderOrderQueryParams, FiltersQueryParameters[FolderFilters]  # type: ignore[misc, valid-type]
):
    text: str | None = Field(
        default=None,
        description="Multi column full text search, across all folders and workspaces",
        max_length=100,
        example="My Project",
    )

    _empty_is_none = validator("text", allow_reuse=True, pre=True)(
        empty_str_to_none_pre_validator
    )

    class Config:
        extra = Extra.forbid


class RemoveQueryParams(BaseModel):
    force: bool = Field(
        default=False, description="Force removal (even if resource is active)"
    )
