""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""

from typing import Any

from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rest_base import RequestParameters
from models_library.rest_filters import Filters, FiltersQueryParameters
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_classes,
)
from models_library.rest_pagination import PageQueryParameters
from models_library.utils.common_validators import (
    empty_str_to_none_pre_validator,
    null_or_none_str_to_none_validator,
)
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, Extra, Field, parse_obj_as, root_validator, validator
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
    X_SIMCORE_USER_AGENT,
)

from .exceptions import WrongTagIdsInQueryError
from .models import ProjectTypeAPI


class ProjectCreateHeaders(BaseModel):

    simcore_user_agent: str = Field(  # type: ignore[literal-required]
        default=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
        description="Optional simcore user agent",
        alias=X_SIMCORE_USER_AGENT,
    )

    parent_project_uuid: ProjectID | None = Field(  # type: ignore[literal-required]
        default=None,
        description="Optional parent project UUID",
        alias=X_SIMCORE_PARENT_PROJECT_UUID,
    )
    parent_node_id: NodeID | None = Field(  # type: ignore[literal-required]
        default=None,
        description="Optional parent node ID",
        alias=X_SIMCORE_PARENT_NODE_ID,
    )

    @root_validator
    @classmethod
    def check_parent_valid(cls, values: dict[str, Any]) -> dict[str, Any]:
        if (
            values.get("parent_project_uuid") is None
            and values.get("parent_node_id") is not None
        ) or (
            values.get("parent_project_uuid") is not None
            and values.get("parent_node_id") is None
        ):
            msg = "Both parent_project_uuid and parent_node_id must be set or both null or both unset"
            raise ValueError(msg)
        return values

    class Config:
        allow_population_by_field_name = False


class ProjectCreateParams(BaseModel):
    from_study: ProjectID | None = Field(
        None,
        description="Option to create a project from existing template or study: from_study={study_uuid}",
    )
    as_template: bool = Field(
        default=False,
        description="Option to create a template from existing project: as_template=true",
    )
    copy_data: bool = Field(
        default=True,
        description="Option to copy data when creating from an existing template or as a template, defaults to True",
    )
    hidden: bool = Field(
        default=False,
        description="Enables/disables hidden flag. Hidden projects are by default unlisted",
    )

    class Config:
        extra = Extra.forbid


class ProjectFilters(Filters):
    trashed: bool | None = Field(
        default=False,
        description="Set to true to list trashed, false to list non-trashed (default), None to list all",
    )


(
    ListProjectsOrderParams,
    ListProjectsOrderParamsOpenApi,
) = create_ordering_query_model_classes(
    ordering_fields={
        "type",
        "uuid",
        "name",
        "description",
        "prj_owner",
        "creation_date",
        "last_change_date",
    },
    default=OrderBy(field=IDStr("last_change_date"), direction=OrderDirection.DESC),
)


class ListProjectsExtraQueryParams(RequestParameters):
    project_type: ProjectTypeAPI = Field(default=ProjectTypeAPI.all, alias="type")
    show_hidden: bool = Field(
        default=False, description="includes projects marked as hidden in the listing"
    )
    search: str | None = Field(
        default=None,
        description="Multi column full text search",
        max_length=100,
        example="My Project",
    )
    folder_id: FolderID | None = Field(
        default=None,
        description="Filter projects in specific folder. Default filtering is a root directory.",
    )
    workspace_id: WorkspaceID | None = Field(
        default=None,
        description="Filter projects in specific workspace. Default filtering is a private workspace.",
    )

    @validator("search", pre=True)
    @classmethod
    def search_check_empty_string(cls, v):
        if not v:
            return None
        return v

    _null_or_none_str_to_none_validator = validator(
        "folder_id", allow_reuse=True, pre=True
    )(null_or_none_str_to_none_validator)

    _null_or_none_str_to_none_validator2 = validator(
        "workspace_id", allow_reuse=True, pre=True
    )(null_or_none_str_to_none_validator)


class ListProjectsQueryParams(
    PageQueryParameters,
    ListProjectsOrderParams,
    FiltersQueryParameters[ProjectFilters],
    ListProjectsExtraQueryParams,
):
    ...


class ProjectActiveParams(BaseModel):
    client_session_id: str


class SearchProjectExtraQueryParams(PageQueryParameters):
    text: str | None = Field(
        default=None,
        description="Multi column full text search, across all folders and workspaces",
        max_length=100,
        example="My Project",
    )
    tag_ids: str | None = Field(
        default=None,
        description="Search by tag ID (multiple tag IDs may be provided separated by column)",
        example="1,3",
    )

    _empty_is_none = validator("text", allow_reuse=True, pre=True)(
        empty_str_to_none_pre_validator
    )


class SearchProjectsQueryParams(SearchProjectExtraQueryParams, ListProjectsOrderParams):
    def tag_ids_list(self) -> list[int]:
        try:
            # Split the tag_ids by commas and map them to integers
            if self.tag_ids:
                tag_ids_list = list(map(int, self.tag_ids.split(",")))
                # Validate that the tag_ids_list is indeed a list of integers
                parse_obj_as(list[int], tag_ids_list)
            else:
                tag_ids_list = []
        except ValueError as exc:
            raise WrongTagIdsInQueryError from exc

        return tag_ids_list
