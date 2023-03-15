from enum import Enum


class VolumeID(str, Enum):
    OUTPUTS = "outputs"
    INPUTS = "inputs"
    STATES = "states"
    SHARED_STORE = "shared_store"
