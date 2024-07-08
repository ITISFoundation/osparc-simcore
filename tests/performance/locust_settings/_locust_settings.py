from datetime import timedelta

from parse import Result, parse
from pydantic import AnyHttpUrl, Field, PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._dump_dotenv import dump_dotenv


def _timedelta_serializer(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h{minutes}m{seconds}s"


class LocustSettings(BaseSettings):
    model_config = SettingsConfigDict(
        cli_parse_args=True, json_encoders={timedelta: _timedelta_serializer}
    )

    LOCUST_HOST: AnyHttpUrl = Field(
        default=..., examples=["https://api.osparc-master.speag.com"]
    )
    LOCUST_USERS: PositiveInt = Field(default=...)
    LOCUST_HEADLESS: bool = Field(default=True)
    LOCUST_PRINT_STATS: bool = Field(default=True)
    LOCUST_SPAWN_RATE: PositiveInt = Field(default=20)
    LOCUST_RUN_TIME: timedelta = Field(default=...)

    @field_validator("LOCUST_RUN_TIME", mode="before")
    @classmethod
    def validate_run_time(cls, v: str):
        result = parse("{hour:d}h{min:d}m{sec:d}s", v)
        if not isinstance(result, Result):
            return v
        hour = result.named.get("hour")
        min = result.named.get("min")
        sec = result.named.get("sec")
        if hour is None or min is None or sec is None:
            raise ValueError("Could not parse time")
        return timedelta(hours=hour, minutes=min, seconds=sec)


if __name__ == "__main__":
    dump_dotenv(LocustSettings())
