from datetime import datetime
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from .projects import ProjectID
from .users import UserID

CommentID: TypeAlias = PositiveInt


class _ProjectsCommentsBase(BaseModel):
    comment_id: CommentID = Field(
        ..., description="Primary key, identifies the comment"
    )
    project_uuid: ProjectID = Field(..., description="project reference for this table")
    user_id: UserID = Field(
        ...,
        description="user reference for this table",
    )
    contents: str = Field(
        ...,
        description="Contents of the comment",
    )
    created: datetime = Field(
        ...,
        description="Timestamp on creation",
    )
    modified: datetime = Field(
        ...,
        description="Timestamp with last update",
    )


class ProjectsCommentsDB(_ProjectsCommentsBase):
    model_config = ConfigDict(extra="forbid")


class ProjectsCommentsAPI(_ProjectsCommentsBase):
    model_config = ConfigDict(extra="forbid")
