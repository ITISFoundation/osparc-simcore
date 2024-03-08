from typing import Any, ClassVar, TypeAlias

from pydantic import BaseModel, NonNegativeFloat


class ActivityInfo(BaseModel):
    seconds_inactive: NonNegativeFloat

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"seconds_inactive": 0},
                {"seconds_inactive": 100},
            ]
        }


ActivityInfoOrNone: TypeAlias = ActivityInfo | None
