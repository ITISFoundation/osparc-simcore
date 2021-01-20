"""
    Models both project and node states
"""

from enum import Enum, unique
from typing import Optional

from pydantic import BaseModel, Extra, Field

from .projects_access import Owner


@unique
class RunningState(str, Enum):
    UNKNOWN = "UNKNOWN"
    PUBLISHED = "PUBLISHED"
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


@unique
class DataState(str, Enum):
    UP_TO_DATE = "UPTODATE"
    OUTDATED = "OUTDATED"


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
    # data: DataState = Field(..., description="The proj current data state")

    class Config:
        extra = Extra.forbid
