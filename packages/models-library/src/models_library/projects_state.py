"""
Models both project and node states
"""

from enum import Enum, unique
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.config import JsonDict

from .groups import GroupID
from .projects_access import Owner


@unique
class RunningState(str, Enum):
    """State of execution of a project's computational workflow

    SEE StateType for task state

    # Computational backend states explained:
    - UNKNOWN - The backend doesn't know about the task anymore, it has disappeared from the system or it was never created (eg. when we are asking for the task)
    - NOT_STARTED - Default state when the task is created
    - PUBLISHED - The task has been submitted to the computational backend (click on "Run" button in the UI)
    - PENDING - Task has been transferred to the Dask scheduler and is waiting for a worker to pick it up (director-v2 --> Dask scheduler)
       - But! it is also transition state (ex. PENDING -> WAITING_FOR_CLUSTER -> PENDING -> WAITING_FOR_RESOURCES -> PENDING -> STARTED)
    - WAITING_FOR_CLUSTER - No cluster (Dask scheduler) is available to run the task; waiting for one to become available
    - WAITING_FOR_RESOURCES - No worker (Dask worker) is available to run the task; waiting for one to become available
    - STARTED - A worker has picked up the task and is executing it
    - SUCCESS - Task finished successfully
    - FAILED - Task finished with an error
    - ABORTED - Task was aborted before completion

    """

    UNKNOWN = "UNKNOWN"
    NOT_STARTED = "NOT_STARTED"
    PUBLISHED = "PUBLISHED"
    PENDING = "PENDING"
    WAITING_FOR_CLUSTER = "WAITING_FOR_CLUSTER"
    WAITING_FOR_RESOURCES = "WAITING_FOR_RESOURCES"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"

    @staticmethod
    def list_running_states() -> list["RunningState"]:
        return [
            RunningState.PUBLISHED,
            RunningState.PENDING,
            RunningState.WAITING_FOR_RESOURCES,
            RunningState.STARTED,
            RunningState.WAITING_FOR_CLUSTER,
        ]

    def is_running(self) -> bool:
        return self in self.list_running_states()


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
    MAINTAINING = "MAINTAINING"  # used for maintenance tasks, like removing EFS data


class ProjectShareState(BaseModel):
    status: Annotated[ProjectStatus, Field(description="The status of the project")]
    locked: Annotated[bool, Field(description="True if the project is locked")]
    current_user_groupids: Annotated[
        list[GroupID],
        Field(
            description="Current users in the project (if the project is locked, the list contains only the lock owner)"
        ),
    ]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "status": ProjectStatus.CLOSED,
                        "locked": False,
                        "current_users": [],
                    },
                    {
                        "status": ProjectStatus.OPENING,
                        "locked": False,
                        "current_users": [
                            "7",
                            "15",
                            "666",
                        ],
                    },
                    {
                        "status": ProjectStatus.OPENED,
                        "locked": False,
                        "current_users": [
                            "7",
                            "15",
                            "666",
                        ],
                    },
                    {
                        "status": ProjectStatus.CLONING,
                        "locked": True,
                        "current_users": [
                            "666",
                        ],
                    },
                ]
            }
        )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra=_update_json_schema_extra,
    )

    @model_validator(mode="after")
    def check_model_valid(self) -> Self:
        self.locked = self.status in [
            ProjectStatus.CLONING,
            ProjectStatus.EXPORTING,
            ProjectStatus.MAINTAINING,
        ]
        if self.locked and not self.current_user_groupids:
            msg = "If the project is locked, the current_users list must contain at least the lock owner"
            raise ValueError(msg)
        if self.status is ProjectStatus.CLOSED:
            if self.locked:
                msg = "If the project is closed, it cannot be locked"
                raise ValueError(msg)
            if self.current_user_groupids:
                msg = "If the project is closed, the current_users list must be empty"
                raise ValueError(msg)
        elif not self.current_user_groupids and (
            self.status is not ProjectStatus.MAINTAINING
        ):
            msg = f"If the project is {self.status=}, the current_users list must not be None"
            raise ValueError(msg)

        return self


class ProjectLocked(BaseModel):
    value: bool = Field(..., description="True if the project is locked")
    status: ProjectStatus = Field(..., description="The status of the project")
    owner: Owner | None = Field(
        default=None,
        description="If locked, the user that owns the lock",
        validate_default=True,
    )
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        json_schema_extra={
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
        },
    )

    @field_validator("status", mode="after")
    @classmethod
    def check_status_compatible(cls, v, info: ValidationInfo):
        if info.data["value"] is False and v not in ["CLOSED", "OPENED"]:
            msg = f"status is set to {v} and lock is set to {info.data['value']}!"
            raise ValueError(msg)
        if info.data["value"] is True and v == "CLOSED":
            msg = f"status is set to {v} and lock is set to {info.data['value']}!"
            raise ValueError(msg)
        return v

    @model_validator(mode="before")
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

    model_config = ConfigDict(extra="forbid")


class ProjectState(BaseModel):
    share_state: Annotated[
        ProjectShareState, Field(description="The project lock state")
    ]
    state: Annotated[
        ProjectRunningState, Field(description="The project running state")
    ]

    model_config = ConfigDict(extra="forbid")
