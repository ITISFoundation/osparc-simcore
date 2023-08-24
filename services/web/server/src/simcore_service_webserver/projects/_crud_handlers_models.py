""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""
import json

from models_library.projects import ProjectID
from models_library.rest_pagination import PageQueryParameters
from pydantic import BaseModel, Extra, Field, validator

from ._crud_api_read import OrderDirection, ProjectListFilters, ProjectOrderBy
from .models import ProjectTypeAPI
from .utils import replace_multiple_spaces


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

    order_by: list[ProjectOrderBy] | None = Field(
        default=None,
        description="Comma separated list of fields for ordering. The default sorting order is ascending. To specify descending order for a field, users append a 'desc' suffix",
        example="foo desc, bar",
    )
    filters: ProjectListFilters | None = Field(
        default=None,
        description="Filters to process on the projects list, encoded as JSON",
        example='{"tags": [1, 5], "classifiers": ["foo", "bar"]}',
    )
    search: str | None = Field(
        default=None,
        description="Multi column full text search",
        max_length=100,
        example="My Project",
    )

    @validator("order_by", pre=True)
    @classmethod
    def sort_by_should_have_special_format(cls, v):
        if not v:
            return v

        parse_fields_with_direction = []
        fields = v.split(",")
        for field in fields:
            field_info = replace_multiple_spaces(field.strip()).split(" ")
            field_name = field_info[0]
            direction = OrderDirection.ASC

            if len(field_info) == 2:
                if field_info[1] == OrderDirection.DESC.value:
                    direction = OrderDirection.DESC
                else:
                    msg = "Field direction in the order_by parameter must contain either 'desc' direction or empty value for 'asc' direction."
                    raise ValueError(msg)

            parse_fields_with_direction.append(
                ProjectOrderBy(field=field_name, direction=direction)
            )

        return parse_fields_with_direction

    @validator("filters", pre=True)
    @classmethod
    def filters_parse_to_object(cls, v):
        if v:
            v = json.loads(v)
        return v

    @validator("search", pre=True)
    @classmethod
    def search_check_empty_string(cls, v):
        if not v:
            return None
        return v

    class Config:
        extra = Extra.forbid


class ProjectActiveParams(BaseModel):
    client_session_id: str
