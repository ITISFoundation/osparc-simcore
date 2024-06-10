import pickle
from dataclasses import dataclass, field
from datetime import timedelta

import arrow
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
)
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.utils.enums import StrAutoEnum, auto_str
from servicelib.deferred_tasks import TaskUID


class UserRequestedState(StrAutoEnum):
    RUNNING = auto_str()
    STOPPED = auto_str()


class SchedulerServiceState(StrAutoEnum):
    # service was started and is running as expected
    RUNNING = auto_str()
    # service is not present
    IDLE = auto_str()
    # something went wrong while starting/stopping service
    UNEXPECTED_OUTCOME = auto_str()

    # service is being started
    STARTING = auto_str()
    # service is being stopped
    STOPPING = auto_str()

    # service status has not been determined
    UNKNOWN = auto_str()


@dataclass
class TrackedServiceModel:  # pylint:disable=too-many-instance-attributes
    # used to create the service in any given moment if the requested_state is RUNNING
    # can be set to None only when stopping the service
    dynamic_service_start: DynamicServiceStart | None

    # required for propagating status changes to the frontend
    user_id: UserID | None
    project_id: ProjectID | None

    # what the user desires (RUNNING or STOPPED)
    requested_state: UserRequestedState

    # set this after parsing the incoming state via the API calls
    current_state: SchedulerServiceState = SchedulerServiceState.UNKNOWN

    #############################
    ### SERVICE STATUS UPDATE ###
    #############################

    # set when a job will be immediately scheduled
    scheduled_to_run: bool = False

    # stored for debug mainly this is used to compute ``current_state``
    service_status: str = ""
    # uid of the job currently fetching the status
    service_status_task_uid: TaskUID | None = None

    # used to determine when to poll the status again
    check_status_after: float = field(
        default_factory=lambda: arrow.utcnow().timestamp()
    )

    def set_check_status_after_to(self, delay_from_now: timedelta) -> None:
        self.check_status_after = (arrow.utcnow() + delay_from_now).timestamp()

    # used to determine when was the last time the status was notified
    last_status_notification: float = 0

    def set_last_status_notification_to_now(self) -> None:
        self.last_status_notification = arrow.utcnow().timestamp()

    #####################
    ### SERIALIZATION ###
    #####################

    def to_bytes(self) -> bytes:
        return pickle.dumps(self)

    @classmethod
    def from_bytes(cls, data: bytes) -> "TrackedServiceModel":
        return pickle.loads(data)  # type: ignore # noqa: S301
