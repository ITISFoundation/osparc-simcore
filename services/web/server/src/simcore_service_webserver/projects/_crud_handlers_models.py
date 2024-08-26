""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""

from typing import Any

from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageQueryParameters
from models_library.utils.common_validators import null_or_none_str_to_none_validator
from pydantic import BaseModel, Extra, Field, Json, root_validator, validator
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
    X_SIMCORE_USER_AGENT,
)

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


class ProjectListParams(PageQueryParameters):
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

    @validator("search", pre=True)
    @classmethod
    def search_check_empty_string(cls, v):
        if not v:
            return None
        return v

    _null_or_none_str_to_none_validator = validator(
        "folder_id", allow_reuse=True, pre=True
    )(null_or_none_str_to_none_validator)


class ProjectListWithJsonStrParams(ProjectListParams):
    order_by: Json[OrderBy] = Field(  # pylint: disable=unsubscriptable-object
        default=OrderBy(field=IDStr("last_change_date"), direction=OrderDirection.DESC),
        description="Order by field (type|uuid|name|description|prj_owner|creation_date|last_change_date) and direction (asc|desc). The default sorting order is ascending.",
        example='{"field": "prj_owner", "direction": "desc"}',
        alias="order_by",
    )

    @validator("order_by", check_fields=False)
    @classmethod
    def validate_order_by_field(cls, v):
        if v.field not in {
            "type",
            "uuid",
            "name",
            "description",
            "prj_owner",
            "creation_date",
            "last_change_date",
        }:
            msg = f"We do not support ordering by provided field {v.field}"
            raise ValueError(msg)
        return v

    class Config:
        extra = Extra.forbid


class ProjectActiveParams(BaseModel):
    client_session_id: str
