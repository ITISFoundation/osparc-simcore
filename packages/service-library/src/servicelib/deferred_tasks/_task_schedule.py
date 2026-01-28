from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated

import arrow
from common_library.basic_types import DEFAULT_FACTORY
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
    timeout: Annotated[
        timedelta,
        Field(description="Amount of time after which the task execution will time out"),
    ]
    class_unique_reference: Annotated[
        ClassUniqueReference,
        Field(
            description="reference to the class containing the code and handlers for the execution of the task",
        ),
    ]
    start_context: Annotated[
        StartContext,
        Field(
            description="data used to assemble the ``StartContext``",
        ),
    ]

    state: Annotated[TaskState, Field(description="represents the execution step of the task")]

    total_attempts: Annotated[
        NonNegativeInt,
        Field(description="maximum number of attempts before giving up (0 means no retries)"),
    ]

    execution_attempts: Annotated[
        NonNegativeInt,
        Field(
            description="remaining attempts to run the code, only retries if this is > 0",
        ),
    ]

    wait_cancellation_until: Annotated[
        datetime | None,
        Field(description="when set has to wait till this before cancelling the task"),
    ] = None

    time_started: Annotated[
        datetime,
        Field(
            default_factory=lambda: arrow.utcnow().datetime,
            description="time when task schedule was created, used for statistics",
        ),
    ] = DEFAULT_FACTORY

    result: Annotated[
        TaskExecutionResult | None,
        Field(
            description=(
                f"Populated by {TaskState.WORKER}. It always has a value after worker handles it.Will be used "
            ),
            discriminator="result_type",
        ),
    ] = None
