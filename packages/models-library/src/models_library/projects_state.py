"""
    Models both project and node states
"""

from enum import Enum, unique
from typing import Optional

from pydantic import BaseModel, Extra, Field, validator

from .projects_access import Owner


@unique
class RunningState(str, Enum):
    """State of execution of a project's computational workflow

    SEE StateType for task state
    """

    UNKNOWN = "UNKNOWN"
    PUBLISHED = "PUBLISHED"
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"

    def is_running(self) -> bool:
        return self in (
            RunningState.PUBLISHED,
            RunningState.PENDING,
            RunningState.STARTED,
            RunningState.RETRY,
        )


@unique
class DataState(str, Enum):
    UP_TO_DATE = "UPTODATE"
    OUTDATED = "OUTDATED"


@unique
class ProjectStatus(str, Enum):
    CLOSED = "CLOSED"
    CLOSING = "CLOSING"
    CLONING = "CLONING"
    EXPORTING = "EXPORTING"
    OPENING = "OPENING"
    OPENED = "OPENED"
    CHECK_IF_LOCKED = "CHECK_IF_LOCKED"


class ProjectLocked(BaseModel):
    value: bool = Field(..., description="True if the project is locked")
    owner: Optional[Owner] = Field(
        default=None, description="If locked, the user that owns the lock"
    )
    status: ProjectStatus = Field(..., description="The status of the project")

    class Config:
        extra = Extra.forbid
        use_enum_values = True
        schema_extra = {
            "examples": [
                {"value": False, "status": ProjectStatus.CLOSED},
                {
                    "value": True,
                    "status": ProjectStatus.OPENED,
                    "owner": {
                        "user_id": 123,
                        "first_name": "Johnny",
                        "last_name": "Cash",
                    },
                },
            ]
        }

    @validator("owner", pre=True, always=True)
    @classmethod
    def check_not_null(cls, v, values):
        if values["value"] is True and v is None:
            raise ValueError("value cannot be None when project is locked")
        return v

    @validator("status", always=True)
    @classmethod
    def check_status_compatible(cls, v, values):
        if values["value"] is False and v not in ["CLOSED", "OPENED"]:
            raise ValueError(
                f"status is set to {v} and lock is set to {values['value']}!"
            )
        if values["value"] is True and v == "CLOSED":
            raise ValueError(
                f"status is set to {v} and lock is set to {values['value']}!"
            )
        return v


class ProjectRunningState(BaseModel):
    value: RunningState = Field(
        ..., description="The running state of the project", examples=["STARTED"]
    )

    class Config:
        extra = Extra.forbid


class ProjectState(BaseModel):
    locked: ProjectLocked = Field(..., description="The project lock state")
    state: ProjectRunningState = Field(..., description="The project running state")

    class Config:
        extra = Extra.forbid
