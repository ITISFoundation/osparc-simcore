from typing import Annotated

from models_library.groups import GroupID
from models_library.projects import ProjectID
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    HttpUrl,
    StringConstraints,
)

from ._base import InputSchema, OutputSchema


class ProjectsGroupsPathParams(BaseModel):
    project_id: ProjectID
    group_id: GroupID
    model_config = ConfigDict(extra="forbid")


class ProjectsGroupsBodyParams(InputSchema):
    read: bool
    write: bool
    delete: bool


class ProjectShare(InputSchema):
    sharee_email: EmailStr
    sharer_message: Annotated[
        str, StringConstraints(max_length=500, strip_whitespace=True)
    ] = ""

    # sharing access
    read: bool
    write: bool
    delete: bool


class ProjectShareAccepted(OutputSchema):
    sharee_email: EmailStr
    confirmation_link: HttpUrl
