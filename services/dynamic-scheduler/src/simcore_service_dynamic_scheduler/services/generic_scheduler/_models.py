from dataclasses import dataclass
from enum import Enum, auto
from typing import Annotated, Any, Final, TypeAlias

from models_library.basic_types import UUIDStr
from models_library.utils.enums import StrAutoEnum
from pydantic import StringConstraints

_NAME_PATTERN: Final[str] = r"^[a-zA-Z0-9_]\w*$"

ScheduleId: TypeAlias = UUIDStr

OperationName: TypeAlias = Annotated[str, StringConstraints(pattern=_NAME_PATTERN)]
StepGroupName: TypeAlias = Annotated[str, StringConstraints(pattern=_NAME_PATTERN)]
StepName: TypeAlias = Annotated[str, StringConstraints(pattern=_NAME_PATTERN)]

# contains all inputs and outpus of each step in the operation
OperationContext: TypeAlias = dict[str, Any]
# the inputs of `execute` or `revert` of a step
RequiredOperationContext: TypeAlias = dict[str, Any]
# the outputs of `execute` or `revert` of a step
ProvidedOperationContext: TypeAlias = dict[str, Any]


class StepStatus(StrAutoEnum):
    # could not find a status for the step (key not in Redis)
    UNKNOWN = auto()

    # in progress statuses
    SCHEDULED = auto()
    CREATED = auto()
    RUNNING = auto()

    # final statuses
    SUCCESS = auto()
    FAILED = auto()
    CANCELLED = auto()


class OperationErrorType(StrAutoEnum):
    FRAMEWORK_ISSUE = auto()
    STEP_ISSUE = auto()


class EventType(StrAutoEnum):
    ON_EXECUTEDD_COMPLETED = auto()
    ON_REVERT_COMPLETED = auto()


@dataclass(frozen=True)
class OperationToStart:
    operation_name: OperationName
    initial_context: OperationContext


class ReservedContextKeys(str, Enum):
    SCHEDULE_ID = "_schedule_id"


ALL_RESERVED_CONTEXT_KEYS: Final[set[str]] = {x.value for x in ReservedContextKeys}
