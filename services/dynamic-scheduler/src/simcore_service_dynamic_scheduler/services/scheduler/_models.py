from enum import auto
from typing import TypeAlias

from models_library.utils.enums import StrAutoEnum

SchedulerOperationName: TypeAlias = str


class DesiredState(StrAutoEnum):
    RUNNING = auto()
    STOPPED = auto()


class OperationType(StrAutoEnum):
    ENFORCE = auto()
    START = auto()
    MONITOR = auto()
    STOP = auto()
