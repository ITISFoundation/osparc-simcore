import logging

from pydantic import BaseModel, ConstrainedFloat, Field, validate_arguments, validator

_logger = logging.getLogger(__name__)

TaskId = str

ProgressMessage = str


class ProgressPercent(ConstrainedFloat):
    ge = 0.0
    le = 1.0


class TaskProgress(BaseModel):
    """
    Helps the user to keep track of the progress. Progress is expected to be
    defined as a float bound between 0.0 and 1.0
    """

    message: ProgressMessage = Field(default="")
    percent: ProgressPercent = Field(default=0.0)

    @validate_arguments
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
                raise ValueError(f"{percent=} must be in range [0.0, 1.0]")
            self.percent = percent

        _logger.debug("Progress update: %s", f"{self}")

    @classmethod
    def create(cls) -> "TaskProgress":
        return cls.parse_obj(dict(message="", percent=0.0))

    @validator("percent")
    @classmethod
    def round_value_to_3_digit(cls, v):
        return round(v, 3)
