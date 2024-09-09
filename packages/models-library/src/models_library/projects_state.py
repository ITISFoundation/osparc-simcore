"""
    Models both project and node states
"""

from enum import Enum, unique

from pydantic import BaseModel, ConfigDict, Field, validator

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


class ProjectLocked(BaseModel):
    value: bool = Field(..., description="True if the project is locked")
    owner: Owner | None = Field(
        default=None, description="If locked, the user that owns the lock"
    )
    status: ProjectStatus = Field(..., description="The status of the project")
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    # TODO[pydantic]: We couldn't refactor the `validator`, please replace it by `field_validator` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-validators for more information.
    @validator("owner", pre=True, always=True)
    @classmethod
    def check_not_null(cls, v, values):
        if values["value"] is True and v is None:
            msg = "value cannot be None when project is locked"
            raise ValueError(msg)
        return v

    # TODO[pydantic]: We couldn't refactor the `validator`, please replace it by `field_validator` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-validators for more information.
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


class ProjectRunningState(BaseModel):
    value: RunningState = Field(
        ..., description="The running state of the project", examples=["STARTED"]
    )
    model_config = ConfigDict(extra="forbid")


class ProjectState(BaseModel):
    locked: ProjectLocked = Field(..., description="The project lock state")
    state: ProjectRunningState = Field(..., description="The project running state")
    model_config = ConfigDict(extra="forbid")
