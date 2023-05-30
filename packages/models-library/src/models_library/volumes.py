from enum import auto

from .utils.enums import StrAutoEnum


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
    """
    Used by the agent to figure out what to do with the data
    present on the volume.
    """

    CONTENT_NEEDS_TO_BE_SAVED = auto()
    CONTENT_WAS_SAVED = auto()
    CONTENT_NO_SAVE_REQUIRED = auto()
