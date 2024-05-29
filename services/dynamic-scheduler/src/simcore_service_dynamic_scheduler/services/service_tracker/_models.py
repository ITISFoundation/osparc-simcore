from dataclasses import dataclass
from enum import auto

import orjson
from models_library.utils.enums import StrAutoEnum


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

    def to_bytes(self) -> bytes:
        return orjson.dumps(self)

    @classmethod
    def from_bytes(cls, json: bytes) -> "TrackedServiceModel":
        return cls(**orjson.loads(json))
