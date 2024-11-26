""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""

from typing import Annotated, Self

from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rest_base import RequestParameters
from models_library.rest_filters import Filters, FiltersQueryParameters
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_class,
)
from models_library.rest_pagination import PageQueryParameters
from models_library.utils.common_validators import (
    empty_str_to_none_pre_validator,
    null_or_none_str_to_none_validator,
)
from models_library.workspaces import WorkspaceID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)
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

    @model_validator(mode="after")
    def check_parent_valid(self) -> Self:
        if (self.parent_project_uuid is None and self.parent_node_id is not None) or (
            self.parent_project_uuid is not None and self.parent_node_id is None
        ):
            msg = "Both parent_project_uuid and parent_node_id must be set or both null or both unset"
            raise ValueError(msg)
        return self

    model_config = ConfigDict(populate_by_name=False)


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
    model_config = ConfigDict(extra="forbid")


class ProjectFilters(Filters):
    trashed: bool | None = Field(
        default=False,
        description="Set to true to list trashed, false to list non-trashed (default), None to list all",
    )


ProjectsListOrderParams = create_ordering_query_model_class(
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


class ProjectsListExtraQueryParams(RequestParameters):
    project_type: ProjectTypeAPI = Field(default=ProjectTypeAPI.all, alias="type")
    show_hidden: bool = Field(
        default=False, description="includes projects marked as hidden in the listing"
    )
    search: str | None = Field(
        default=None,
        description="Multi column full text search",
        max_length=100,
        examples=["My Project"],
    )
    folder_id: FolderID | None = Field(
        default=None,
        description="Filter projects in specific folder. Default filtering is a root directory.",
    )
    workspace_id: WorkspaceID | None = Field(
        default=None,
        description="Filter projects in specific workspace. Default filtering is a private workspace.",
    )

    @field_validator("search", mode="before")
    @classmethod
    def search_check_empty_string(cls, v):
        if not v:
            return None
        return v

    _null_or_none_str_to_none_validator = field_validator("folder_id", mode="before")(
        null_or_none_str_to_none_validator
    )

    _null_or_none_str_to_none_validator2 = field_validator(
        "workspace_id", mode="before"
    )(null_or_none_str_to_none_validator)


class ProjectsListQueryParams(
    PageQueryParameters,
    ProjectsListOrderParams,  # type: ignore[misc, valid-type]
    FiltersQueryParameters[ProjectFilters],
    ProjectsListExtraQueryParams,
):
    ...


class ProjectActiveQueryParams(BaseModel):
    client_session_id: str


class ProjectSearchExtraQueryParams(PageQueryParameters):
    text: str | None = Field(
        default=None,
        description="Multi column full text search, across all folders and workspaces",
        max_length=100,
        examples=["My Project"],
    )
    tag_ids: Annotated[
        str | None,
        Field(
            default=None,
            description="Search by tag ID (multiple tag IDs may be provided separated by column)",
            examples=["1,3"],
        ),
    ]

    _empty_is_none = field_validator("text", mode="before")(
        empty_str_to_none_pre_validator
    )


class ProjectsSearchQueryParams(
    ProjectSearchExtraQueryParams, ProjectsListOrderParams  # type: ignore[misc, valid-type]
):
    def tag_ids_list(self) -> list[int]:
        try:
            # Split the tag_ids by commas and map them to integers
            if self.tag_ids:
                tag_ids_list = list(map(int, self.tag_ids.split(",")))
                # Validate that the tag_ids_list is indeed a list of integers
                TypeAdapter(list[int]).validate_python(tag_ids_list)
            else:
                tag_ids_list = []
        except ValueError as exc:
            raise WrongTagIdsInQueryError from exc

        return tag_ids_list
