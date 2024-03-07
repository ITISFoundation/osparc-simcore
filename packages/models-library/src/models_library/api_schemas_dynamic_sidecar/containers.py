from typing import TypeAlias

from pydantic import BaseModel, NonNegativeFloat


class ActivityInfo(BaseModel):
    seconds_inactive: NonNegativeFloat


ActivityInfoOrNone: TypeAlias = ActivityInfo | None
