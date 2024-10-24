"""
    Models both project and node states
"""

from enum import Enum, unique
from typing import Any, ClassVar

from pydantic import BaseModel, Extra, Field, root_validator, validator

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
    WAITING_FOR_RESOURCES = "WAITING_FOR_RESOURCES"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    WAITING_FOR_CLUSTER = "WAITING_FOR_CLUSTER"

    def is_running(self) -> bool:
        return self in (
            RunningState.PUBLISHED,
            RunningState.PENDING,
            RunningState.WAITING_FOR_RESOURCES,
            RunningState.STARTED,
            RunningState.WAITING_FOR_CLUSTER,
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
    MAINTAINING = "MAINTAINING"


class ProjectLocked(BaseModel):
    value: bool = Field(..., description="True if the project is locked")
    status: ProjectStatus = Field(..., description="The status of the project")
    owner: Owner | None = Field(
        default=None, description="If locked, the user that owns the lock"
    )

    class Config:
        extra = Extra.forbid
        use_enum_values = True
        schema_extra: ClassVar[dict[str, Any]] = {
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

    @validator("status", always=True)
    @classmethod
    def check_status_compatible(cls, v, values):
        if values["value"] is False and v not in ["CLOSED", "OPENED"]:
            msg = f"status is set to {v} and lock is set to {values['value']}!"
            raise ValueError(msg)
        if values["value"] is True and v == "CLOSED":
            msg = f"status is set to {v} and lock is set to {values['value']}!"
            raise ValueError(msg)
        return v

    @root_validator(pre=True)
    @classmethod
    def check_owner_compatible(cls, values):
        if (
            values["value"] is True
            and values.get("owner") is None
            and values["status"]
            in [
                status.value
                for status in ProjectStatus
                if status != ProjectStatus.MAINTAINING
            ]
        ):
            msg = "Owner must be specified when the project is not in the 'MAINTAINING' status."
            raise ValueError(msg)
        return values


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
