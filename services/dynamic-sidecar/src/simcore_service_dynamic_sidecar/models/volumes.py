from datetime import datetime
from enum import auto

import arrow
from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, Field


class VolumeCategory(StrAutoEnum):
    """
    These uniquely identify volumes which are mounted by
    the dynamic-sidecar and user services.
    This is primarily used to keep track of the status of
    each individual volume on the volumes.
    The status is ingested by the agent and processed
    when the volume is removed.
    """

    # contains data relative to output ports
    OUTPUTS = auto()

    # contains data relative to input ports
    INPUTS = auto()

    # contains files which represent the state of the service
    # usually the user's workspace
    STATES = auto()

    # contains dynamic-sidecar data required to maintain state
    # between restarts
    SHARED_STORE = auto()


class VolumeStatus(StrAutoEnum):
    CONTENT_NEEDS_TO_BE_SAVED = auto()
    CONTENT_WAS_SAVED = auto()
    CONTENT_NO_SAVE_REQUIRED = auto()


class VolumeState(BaseModel):
    status: VolumeStatus
    last_changed: datetime = Field(default_factory=lambda: arrow.utcnow().datetime)

    def __eq__(self, other: object) -> bool:
        # only include status for equality last_changed is not important
        is_equal: bool = self.status == getattr(other, "status", None)
        return is_equal
