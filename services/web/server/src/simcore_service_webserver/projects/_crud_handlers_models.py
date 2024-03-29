""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""

from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageQueryParameters
from pydantic import BaseModel, Extra, Field, Json, validator

from .models import ProjectTypeAPI


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

    @validator("search", pre=True)
    @classmethod
    def search_check_empty_string(cls, v):
        if not v:
            return None
        return v


class ProjectListWithJsonStrParams(ProjectListParams):
    order_by: Json[OrderBy] = Field(  # pylint: disable=unsubscriptable-object
        default=OrderBy(field="last_change_date", direction=OrderDirection.DESC),
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
            raise ValueError(f"We do not support ordering by provided field {v.field}")
        return v

    class Config:
        extra = Extra.forbid


class ProjectActiveParams(BaseModel):
    client_session_id: str
