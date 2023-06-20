from datetime import datetime
from typing import TypeAlias

from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import BaseModel, Extra, Field, PositiveInt

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
    content: str = Field(
        ...,
        description="Content of the comment",
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
    class Config:
        extra = Extra.forbid


class ProjectsCommentsAPI(_ProjectsCommentsBase):
    class Config:
        extra = Extra.forbid
        # Currently, the DB and API is one to one and is already validated when coming from the DB
        validation = False
