from typing import Annotated

from pydantic import BaseModel, Field

from .basic_types import IDStr


class MetadataFilterItem(BaseModel):
    key: IDStr
    value: Annotated[str | None, Field(description="SQL-like pattern")]


class ListProjectsMarkedAsJobFilter(BaseModel):
    job_parent_resource_name_prefix: str | None
    any_of_metadata: list[MetadataFilterItem] | None = None

    # TODO: early validation of filters
    # TODO: update interface to list_projects_marked_as_jobs
