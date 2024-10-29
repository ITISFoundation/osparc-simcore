from datetime import timedelta
from enum import auto

import arrow
import umsgpack  # type: ignore[import-untyped]
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
)
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, Field
from servicelib.deferred_tasks import TaskUID


class UserRequestedState(StrAutoEnum):
    RUNNING = auto()
    STOPPED = auto()


class SchedulerServiceState(StrAutoEnum):
    # service was started and is running as expected
    RUNNING = auto()
    # service is not present
    IDLE = auto()
    # something went wrong while starting/stopping service
    UNEXPECTED_OUTCOME = auto()

    # service is being started
    STARTING = auto()
    # service is being stopped
    STOPPING = auto()

    # service status has not been determined
    UNKNOWN = auto()


class TrackedServiceModel(BaseModel):  # pylint:disable=too-many-instance-attributes

    dynamic_service_start: DynamicServiceStart | None = Field(
        description=(
            "used to create the service in any given moment if the requested_state is RUNNING"
            "can be set to None only when stopping the service"
        )
    )

    user_id: UserID | None = Field(
        description="required for propagating status changes to the frontend"
    )
    project_id: ProjectID | None = Field(
        description="required for propagating status changes to the frontend"
    )

    requested_state: UserRequestedState = Field(
        description=("status of the service desidered by the user RUNNING or STOPPED")
    )

    _current_state: SchedulerServiceState = Field(
        default=SchedulerServiceState.UNKNOWN,
        description="to set after parsing the incoming state via the API calls",
    )

    @property
    def current_state(self) -> SchedulerServiceState:
        return self._current_state

    @current_state.setter
    def current_state(self, new_value: SchedulerServiceState) -> None:
        if new_value == self._current_state:
            return  # no action is taken if the value is the same

        self._current_state = new_value
        self.last_state_change = arrow.utcnow().timestamp()

    last_state_change: float = Field(
        default_factory=lambda: arrow.utcnow().timestamp(),
        metadata={"description": "keeps track when the current_state was last updated"},
    )

    #############################
    ### SERVICE STATUS UPDATE ###
    #############################

    scheduled_to_run: bool = Field(
        default=False,
        description="set when a job will be immediately scheduled",
    )

    service_status: str = Field(
        default="",
        description="stored for debug mainly this is used to compute ``current_state``",
    )
    service_status_task_uid: TaskUID | None = Field(
        default=None,
        description="uid of the job currently fetching the status",
    )

    check_status_after: float = Field(
        default_factory=lambda: arrow.utcnow().timestamp(),
        description="used to determine when to poll the status again",
    )

    last_status_notification: float = Field(
        default=0,
        description="used to determine when was the last time the status was notified",
    )

    def set_check_status_after_to(self, delay_from_now: timedelta) -> None:
        self.check_status_after = (arrow.utcnow() + delay_from_now).timestamp()

    def set_last_status_notification_to_now(self) -> None:
        self.last_status_notification = arrow.utcnow().timestamp()

    #####################
    ### SERIALIZATION ###
    #####################

    def to_bytes(self) -> bytes:
        return umsgpack.packb(self.dict())

    @classmethod
    def from_bytes(cls, data: bytes) -> "TrackedServiceModel":
        unpacked_data = umsgpack.unpackb(data)
        return cls(**unpacked_data)
