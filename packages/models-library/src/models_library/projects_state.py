from typing import Optional
from pydantic import BaseModel, Field, PositiveInt, Extra

from enum import Enum


class RunningState(str, Enum):
    UNKNOWN = "UNKNOWN"
    PUBLISHED = "PUBLISHED"
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ABORTED = "ABORTED"


class Owner(BaseModel):
    user_id: PositiveInt = Field(
        ...,
        description="Owner's identifier when registered in the user's database table",
        examples=[2],
    )
    first_name: str = Field(..., description="Owner first name", examples=["John"])
    last_name: str = Field(..., description="Owner last name", examples=["Smith"])

    class Config:
        extra = Extra.forbid


class ProjectLocked(BaseModel):
    value: bool = Field(
        ..., description="True if the project is locked by another user"
    )
    owner: Optional[Owner] = Field(None, description="The user that owns the lock")

    class Config:
        extra = Extra.forbid


class ProjectRunningState(BaseModel):
    value: RunningState = Field(
        ..., description="The running state of the project", examples=["STARTED"]
    )

    class Config:
        extra = Extra.forbid


class ProjectState(BaseModel):
    locked: ProjectLocked = Field(..., description="The project lock state")
    state: ProjectRunningState = Field(..., description="The project running state")
