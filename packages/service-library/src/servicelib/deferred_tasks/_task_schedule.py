from datetime import datetime, timedelta
from enum import Enum

import arrow
from pydantic import BaseModel, Field, NonNegativeInt

from ._base_deferred_handler import StartContext
from ._models import ClassUniqueReference, TaskExecutionResult


class TaskState(str, Enum):
    # entrypoint state
    SCHEDULED = "SCHEDULED"

    SUBMIT_TASK = "SUBMIT_TASK"
    WORKER = "WORKER"
    ERROR_RESULT = "ERROR_RESULT"

    # end states
    DEFERRED_RESULT = "DEFERRED_RESULT"
    FINISHED_WITH_ERROR = "FINISHED_WITH_ERROR"
    MANUALLY_CANCELLED = "MANUALLY_CANCELLED"


class TaskScheduleModel(BaseModel):
    timeout: timedelta = Field(
        ..., description="Amount of time after which the task execution will time out"
    )
    class_unique_reference: ClassUniqueReference = Field(
        ...,
        description="reference to the class containing the code and handlers for the execution of the task",
    )
    start_context: StartContext = Field(
        ...,
        description="data used to assemble the ``StartContext``",
    )

    state: TaskState = Field(
        ..., description="represents the execution step of the task"
    )

    execution_attempts: NonNegativeInt = Field(
        ...,
        description="remaining attempts to run the code, only retries if this is > 0",
    )

    time_started: datetime = Field(
        default_factory=lambda: arrow.utcnow().datetime,
        description="time when task schedule was created, used for statistics",
    )

    result: TaskExecutionResult | None = Field(
        default=None,
        description=(
            f"Populated by {TaskState.WORKER}. It always has a value after worker handles it."
            "Will be used "
        ),
        discriminator="result_type",
    )
