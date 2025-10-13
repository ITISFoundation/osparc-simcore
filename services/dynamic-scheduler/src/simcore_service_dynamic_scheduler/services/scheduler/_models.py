from enum import auto

from models_library.utils.enums import StrAutoEnum


class DesiredState(StrAutoEnum):
    RUNNING = auto()
    STOPPED = auto()


class OperationType(StrAutoEnum):
    ENFORCE = auto()
    START = auto()
    MONITOR = auto()
    STOP = auto()
