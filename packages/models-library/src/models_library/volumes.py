from enum import auto

from .utils.enums import StrAutoEnum


class VolumeCategory(StrAutoEnum):
    OUTPUTS = auto()
    INPUTS = auto()
    STATES = auto()
    SHARED_STORE = auto()
