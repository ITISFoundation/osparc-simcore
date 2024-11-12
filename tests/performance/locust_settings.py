# pylint: disable=unused-argument
# pylint: disable=no-self-use
# pylint: disable=no-name-in-module

import json
from datetime import timedelta
from pathlib import Path
from typing import Final

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

_TEST_DIR: Final[Path] = Path(__file__).parent.resolve()
_LOCUST_FILES_DIR: Final[Path] = _TEST_DIR / "locust_files"
assert _TEST_DIR.is_dir()
assert _LOCUST_FILES_DIR.is_dir()


class LocustSettings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True)

    LOCUST_CHECK_AVG_RESPONSE_TIME: PositiveInt = Field(default=200)
    LOCUST_CHECK_FAIL_RATIO: PositiveFloat = Field(default=0.01, ge=0.0, le=1.0)
    LOCUST_HEADLESS: bool = Field(default=True)
    LOCUST_HOST: AnyHttpUrl = Field(
        default=...,
        examples=["https://api.osparc-master.speag.com"],
    )
    LOCUST_LOCUSTFILE: Path = Field(
        default=...,
        description="Test file. Path should be relative to `locust_files` dir",
    )
    LOCUST_PRINT_STATS: bool = Field(default=True)
    LOCUST_RUN_TIME: timedelta
    LOCUST_SPAWN_RATE: PositiveInt = Field(default=20)

    # Timescale: Log and graph results using TimescaleDB and Grafana dashboards
    # SEE https://github.com/SvenskaSpel/locust-plugins/tree/master/locust_plugins/dashboards
    #
    LOCUST_TIMESCALE: NonNegativeInt = Field(
        default=1,
        ge=0,
        le=1,
        description="Send locust data to Timescale db for reading in Grafana dashboards",
    )
    LOCUST_USERS: PositiveInt = Field(
        default=...,
        description="Number of locust users you want to spawn",
    )

    PGHOST: str = Field(default="postgres")
    PGPASSWORD: str = Field(default="password")
    PGPORT: int = Field(default=5432)
    PGUSER: str = Field(default="postgres")

    @field_validator("LOCUST_RUN_TIME", mode="before")
    @classmethod
    def _validate_run_time(cls, v: str) -> str | timedelta:
        result = parse("{hour:d}h{min:d}m{sec:d}s", v)
        if not isinstance(result, Result):
            return v
        hour = result.named.get("hour")
        _min = result.named.get("min")
        sec = result.named.get("sec")
        if hour is None or _min is None or sec is None:
            msg = "Could not parse time"
            raise ValueError(msg)
        return timedelta(hours=hour, minutes=_min, seconds=sec)

    @field_validator("LOCUST_LOCUSTFILE", mode="after")
    @classmethod
    def _validate_locust_file(cls, v: Path) -> Path:
        v = v.resolve()
        if not v.is_file():
            msg = f"{v} must be an existing file"
            raise ValueError(msg)
        if not v.is_relative_to(_LOCUST_FILES_DIR):
            msg = f"{v} must be a test file relative to {_LOCUST_FILES_DIR}"
            raise ValueError(msg)
        return v.relative_to(_TEST_DIR)

    @field_serializer("LOCUST_RUN_TIME")
    def _serialize_run_time(self, td: timedelta, info: SerializationInfo) -> str:
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h{minutes}m{seconds}s"

    @field_serializer("LOCUST_HOST")
    def _serialize_host(self, url: AnyHttpUrl, info: SerializationInfo) -> str:
        # added as a temporary fix for https://github.com/pydantic/pydantic/issues/7186
        s = f"{url}"
        return s.rstrip("/")


if __name__ == "__main__":
    settings = LocustSettings()
    env_vars = [
        f"{key}={val}" for key, val in json.loads(settings.model_dump_json()).items()
    ]
    print("\n".join(env_vars))
