from enum import Enum
from typing import Any, TypeAlias

ScheduleId: TypeAlias = str
OperationName: TypeAlias = str
StepGroupName: TypeAlias = str
StepName: TypeAlias = str

OperationContext: TypeAlias = dict[str, Any]
ProvidedOperationContext: TypeAlias = dict[str, Any]
RequiredOperationContext: TypeAlias = dict[str, Any]


class StepStatus(str, Enum):
    # could not determine the status
    UNKNOWN = "UNKNOWN"  # could not find a status for the step (used when the key is not present in Redis)

    # in progress status
    SCHEDULED = "SCHEDULED"  # defrred will soon be created
    CREATED = "CREATED"  # do nothing
    RUNNING = "RUNNING"  # do nothing

    # final status
    SUCCESS = "SUCCESS"  # check for next step
    FAILED = "FAILED"  # creating = revert  | destorying = SIGNAL SOMETHING WENT WRONG (this should not happen)
    CANCELLED = "CANCELLED"  # creating = revert | destorying = SIGNAL SOMETHING WENT WRONG (this should not happen)


class OperationErrorType(str, Enum):
    FRAMEWORK_ISSUE = "FRAMEWORK_ISSUE"  # something is wrong with the framework
    STEP_ISSUE = "STEP_ISSUE"  # something is wrong with the user defined step code
