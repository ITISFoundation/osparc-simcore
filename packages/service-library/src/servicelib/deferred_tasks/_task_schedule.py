from datetime import datetime, timedelta
from enum import auto

import arrow
from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, Field, NonNegativeInt

from ._base_deferred_handler import UserStartContext
from ._models import ClassUniqueReference, TaskExecutionResult


class TaskState(StrAutoEnum):
    # entrypoint state
    SCHEDULED = auto()

    SUBMIT_TASK = auto()
    WORKER = auto()
    ERROR_RESULT = auto()

    # end states
    DEFERRED_RESULT = auto()
    FINISHED_WITH_ERROR = auto()
    MANUALLY_CANCELLED = auto()


class TaskSchedule(BaseModel):
    timeout: timedelta = Field(
        ..., description="Amount of time after which the task execution will time out"
    )
    class_unique_reference: ClassUniqueReference = Field(
        ...,
        description="reference to the class containing the code and handlers for the execution of the task",
    )
    user_start_context: UserStartContext = Field(
        ...,
        description="data used to assemble the ``StartContext``",
    )

    state: TaskState = Field(
        ..., description="represents the execution step of the task"
    )

    remaining_retries: NonNegativeInt = Field(
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
    )
