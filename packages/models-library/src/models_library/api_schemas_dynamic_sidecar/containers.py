from pydantic import BaseModel, ConfigDict, NonNegativeFloat


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


type ActivityInfoOrNone = ActivityInfo | None

type DockerComposeYamlStr = str
