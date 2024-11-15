import logging
from typing import Annotated

from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.rest_filters import Filters, FiltersQueryParameters
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageQueryParameters
from models_library.users import UserID
from models_library.utils.common_validators import (
    empty_str_to_none_pre_validator,
    null_or_none_str_to_none_validator,
)
from models_library.workspaces import WorkspaceID
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    Json,
    field_validator,
)
from servicelib.aiohttp.requests_validation import RequestParams, StrictRequestParams
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY

_logger = logging.getLogger(__name__)


class FoldersRequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


class FoldersPathParams(StrictRequestParams):
    folder_id: FolderID


class FolderFilters(Filters):
    trashed: bool | None = Field(
        default=False,
        description="Set to true to list trashed, false to list non-trashed (default), None to list all",
    )


class FolderListSortParams(BaseModel):
    # pylint: disable=unsubscriptable-object
    order_by: Json[OrderBy] = Field(
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
        description="Order by field (modified_at|name|description) and direction (asc|desc). The default sorting order is ascending.",
        examples=['{"field": "name", "direction": "desc"}'],
        alias="order_by",
    )

    @field_validator("order_by", check_fields=False)
    @classmethod
    def _validate_order_by_field(cls, v):
        if v.field not in {
            "modified_at",
            "name",
            "description",
        }:
            msg = f"We do not support ordering by provided field {v.field}"
            raise ValueError(msg)
        if v.field == "modified_at":
            v.field = "modified"
        return v

    model_config = ConfigDict(extra="forbid")


class FolderListWithJsonStrQueryParams(
    PageQueryParameters, FolderListSortParams, FiltersQueryParameters[FolderFilters]
):
    folder_id: Annotated[
        FolderID | None, BeforeValidator(null_or_none_str_to_none_validator)
    ] = Field(
        default=None,
        description="List the subfolders of this folder. By default, list the subfolders of the root directory (Folder ID is None).",
    )
    workspace_id: Annotated[
        WorkspaceID | None, BeforeValidator(null_or_none_str_to_none_validator)
    ] = Field(
        default=None,
        description="List folders in specific workspace. By default, list in the user private workspace",
    )

    model_config = ConfigDict(extra="forbid")


class FolderListFullSearchWithJsonStrQueryParams(
    PageQueryParameters, FolderListSortParams, FiltersQueryParameters[FolderFilters]
):
    text: Annotated[
        str | None, BeforeValidator(empty_str_to_none_pre_validator)
    ] = Field(
        default=None,
        description="Multi column full text search, across all folders and workspaces",
        max_length=100,
        examples=["My Project"],
    )

    model_config = ConfigDict(extra="forbid")


class RemoveQueryParams(BaseModel):
    force: bool = Field(
        default=False, description="Force removal (even if resource is active)"
    )
