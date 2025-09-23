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
    # could not find a status for the step (key not in Redis)
    UNKNOWN = "UNKNOWN"

    # in progress statuses
    SCHEDULED = "SCHEDULED"
    CREATED = "CREATED"
    RUNNING = "RUNNING"

    # final statuses
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OperationErrorType(str, Enum):
    FRAMEWORK_ISSUE = "FRAMEWORK_ISSUE"
    STEP_ISSUE = "STEP_ISSUE"
