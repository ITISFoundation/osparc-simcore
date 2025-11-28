from enum import auto

from models_library.utils.enums import StrAutoEnum

type SchedulerOperationName = str


class DesiredState(StrAutoEnum):
    RUNNING = auto()
    STOPPED = auto()


class OperationType(StrAutoEnum):
    ENFORCE = auto()
    START = auto()
    MONITOR = auto()
    STOP = auto()


class SchedulingProfile(StrAutoEnum):
    LEGACY = auto()
    NEW_STYLE = auto()
