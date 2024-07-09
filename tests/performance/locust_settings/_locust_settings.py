from datetime import timedelta

from parse import Result, parse
from pydantic import (
    AnyHttpUrl,
    Field,
    PositiveFloat,
    PositiveInt,
    SerializationInfo,
    field_serializer,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._dump_dotenv import dump_dotenv


def _timedelta_serializer(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h{minutes}m{seconds}s"


def _remove_trailing_backslash(url: AnyHttpUrl):
    s = f"{url}"
    return s.rstrip("/")


class LocustSettings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True)

    LOCUST_HOST: AnyHttpUrl = Field(
        default=..., examples=["https://api.osparc-master.speag.com"]
    )
    LOCUST_USERS: PositiveInt = Field(default=...)
    LOCUST_HEADLESS: bool = Field(default=True)
    LOCUST_PRINT_STATS: bool = Field(default=True)
    LOCUST_SPAWN_RATE: PositiveInt = Field(default=20)
    LOCUST_RUN_TIME: timedelta = Field(default=...)
    LOCUST_CHECK_AVG_RESPONSE_TIME: PositiveInt = Field(default=200)
    LOCUST_CHECK_FAIL_RATIO: PositiveFloat = Field(default=0.01, ge=0.0, le=1.0)

    @field_validator("LOCUST_RUN_TIME", mode="before")
    @classmethod
    def validate_run_time(cls, v: str) -> str | timedelta:
        result = parse("{hour:d}h{min:d}m{sec:d}s", v)
        if not isinstance(result, Result):
            return v
        hour = result.named.get("hour")
        min = result.named.get("min")
        sec = result.named.get("sec")
        if hour is None or min is None or sec is None:
            raise ValueError("Could not parse time")
        return timedelta(hours=hour, minutes=min, seconds=sec)

    @field_serializer("LOCUST_RUN_TIME")
    def serialize_run_time(self, td: timedelta, info: SerializationInfo) -> str:
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h{minutes}m{seconds}s"

    @field_serializer("LOCUST_HOST")
    def serialize_host(self, url: AnyHttpUrl, info: SerializationInfo) -> str:
        # added as a temporary fix for https://github.com/pydantic/pydantic/issues/7186
        s = f"{url}"
        return s.rstrip("/")


if __name__ == "__main__":
    dump_dotenv(LocustSettings())
