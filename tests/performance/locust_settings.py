# pylint: disable=unused-argument
# pylint: disable=no-self-use
# pylint: disable=no-name-in-module

import json
from datetime import timedelta
from pathlib import Path

from parse import Result, parse
from pydantic import (
    AnyHttpUrl,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    SerializationInfo,
    field_serializer,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class LocustSettings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True)

    LOCUST_CHECK_AVG_RESPONSE_TIME: PositiveInt = Field(default=200)
    LOCUST_CHECK_FAIL_RATIO: PositiveFloat = Field(default=0.01, ge=0.0, le=1.0)
    LOCUST_HEADLESS: bool = Field(default=True)
    LOCUST_HOST: AnyHttpUrl = Field(
        default=..., examples=["https://api.osparc-master.speag.com"]
    )
    LOCUST_LOCUSTFILE: Path = Field(default=...)
    LOCUST_PRINT_STATS: bool = Field(default=True)
    LOCUST_RUN_TIME: timedelta = Field(default=...)
    LOCUST_SPAWN_RATE: PositiveInt = Field(default=20)
    LOCUST_TIMESCALE: NonNegativeInt = Field(default=1, ge=0, le=1)
    LOCUST_USERS: PositiveInt = Field(default=...)

    PGHOST: str = Field(default="postgres")
    PGPASSWORD: str = Field(default="password")
    PGPORT: int = Field(default=5432)
    PGUSER: str = Field(default="postgres")

    @field_validator("LOCUST_RUN_TIME", mode="before")
    @classmethod
    def validate_run_time(cls, v: str) -> str | timedelta:
        result = parse("{hour:d}h{min:d}m{sec:d}s", v)
        if not isinstance(result, Result):
            return v
        hour = result.named.get("hour")
        _min = result.named.get("min")
        sec = result.named.get("sec")
        if hour is None or _min is None or sec is None:
            raise ValueError("Could not parse time")
        return timedelta(hours=hour, minutes=_min, seconds=sec)

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
    settings = LocustSettings()
    result = [
        f"{key}={val}" for key, val in json.loads(settings.model_dump_json()).items()
    ]
    print("\n".join(result))
