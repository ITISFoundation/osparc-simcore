from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, NonNegativeFloat


class ActivityInfo(BaseModel):
    seconds_inactive: NonNegativeFloat
    model_config = ConfigDict()


ActivityInfoOrNone: TypeAlias = ActivityInfo | None
