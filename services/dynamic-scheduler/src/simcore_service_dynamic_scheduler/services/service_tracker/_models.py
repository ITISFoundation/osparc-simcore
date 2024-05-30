from dataclasses import dataclass
from enum import auto
from typing import Final

import arrow
import orjson
from models_library.utils.enums import StrAutoEnum
from servicelib.deferred_tasks import TaskUID

_SECONDS_TO_TRIGGER_SERVICE_CHECKING: Final[float] = 1e6


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
    current_state: ServiceStates = ServiceStates.UNKNOWN

    # stored for debug mainly this is used to compute ``current_state``
    service_status: str = ""
    service_status_task_uid: TaskUID | None = None

    last_checked: float | None = None

    def set_last_checked_to_now(self) -> None:
        self.last_checked = arrow.utcnow().timestamp()

    def seconds_since_last_check(self) -> float:
        return (
            arrow.utcnow().timestamp() - self.last_checked
            if self.last_checked
            else _SECONDS_TO_TRIGGER_SERVICE_CHECKING
        )

    def to_bytes(self) -> bytes:
        return orjson.dumps(self)

    @classmethod
    def from_bytes(cls, json: bytes) -> "TrackedServiceModel":
        return cls(**orjson.loads(json))
