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

    OUTPUTS = auto()
    INPUTS = auto()
    STATES = auto()
    SHARED_STORE = auto()
