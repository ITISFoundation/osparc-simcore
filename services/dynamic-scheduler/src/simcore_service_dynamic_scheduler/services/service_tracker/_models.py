import pickle
from dataclasses import dataclass, field
from datetime import timedelta
from enum import auto

import arrow
from models_library.utils.enums import StrAutoEnum
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


@dataclass
class TrackedServiceModel:
    # what the user desires (RUNNING or STOPPED)
    requested_sate: UserRequestedState

    # set this after parsing the incoming state via the API calls
    current_state: SchedulerServiceState = SchedulerServiceState.UNKNOWN  # type: ignore

    #############################
    ### SERVICE STATSU UPDATE ###
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
        return pickle.loads(data)  # noqa: S301
