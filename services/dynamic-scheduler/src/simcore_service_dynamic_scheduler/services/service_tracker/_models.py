import pickle
from dataclasses import dataclass
from datetime import timedelta
from enum import auto

import arrow
from models_library.utils.enums import StrAutoEnum
from servicelib.deferred_tasks import TaskUID


class UserRequestedState(StrAutoEnum):
    RUNNING = auto()
    STOPPED = auto()


class ServiceStates(StrAutoEnum):
    RUNNING = auto()
    STOPPED = auto()

    STARTING = auto()
    STOPPING = auto()

    UNKNOWN = auto()


@dataclass
class TrackedServiceModel:
    # what the user desires (RUNNING or STOPPED)
    requested_sate: UserRequestedState

    # set this after parsing the incoming state via the API calls
    current_state: ServiceStates = ServiceStates.UNKNOWN  # type: ignore

    # stored for debug mainly this is used to compute ``current_state``
    service_status: str = ""
    service_status_task_uid: TaskUID | None = None

    check_status_after: float | None = None

    def set_check_status_after_to(self, delay: timedelta) -> None:
        self.check_status_after = (arrow.utcnow() + delay).timestamp()

    def to_bytes(self) -> bytes:
        return pickle.dumps(self)

    @classmethod
    def from_bytes(cls, data: bytes) -> "TrackedServiceModel":
        return pickle.loads(data)  # noqa: S301
