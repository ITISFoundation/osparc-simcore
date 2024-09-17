import logging
from typing import Annotated, TypeAlias

from pydantic import BaseModel, Field, field_validator, validate_call

_logger = logging.getLogger(__name__)

TaskId = str

ProgressMessage: TypeAlias = str

ProgressPercent: TypeAlias = Annotated[float, Field(ge=0.0, le=1.0)]


class TaskProgress(BaseModel):
    """
    Helps the user to keep track of the progress. Progress is expected to be
    defined as a float bound between 0.0 and 1.0
    """

    task_id: TaskId | None = Field(default=None)
    message: ProgressMessage = Field(default="")
    percent: ProgressPercent = Field(default=0.0)

    @validate_call
    def update(
        self,
        *,
        message: ProgressMessage | None = None,
        percent: ProgressPercent | None = None,
    ) -> None:
        """`percent` must be between 0.0 and 1.0 otherwise ValueError is raised"""
        if message:
            self.message = message
        if percent:
            if not (0.0 <= percent <= 1.0):
                msg = f"percent={percent!r} must be in range [0.0, 1.0]"
                raise ValueError(msg)
            self.percent = percent

        _logger.debug("Progress update: %s", f"{self}")

    @classmethod
    def create(cls, task_id: TaskId | None = None) -> "TaskProgress":
        return cls(task_id=task_id)

    @field_validator("percent")
    @classmethod
    def round_value_to_3_digit(cls, v):
        return round(v, 3)
