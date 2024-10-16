from typing import Final, TypeAlias

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, TypeAdapter


class ActivityInfo(BaseModel):
    seconds_inactive: NonNegativeFloat
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"seconds_inactive": 0},
                {"seconds_inactive": 100},
            ]
        }
    )


ActivityInfoAdapter: Final[TypeAdapter[ActivityInfo]] = TypeAdapter(ActivityInfo)


ActivityInfoOrNone: TypeAlias = ActivityInfo | None
