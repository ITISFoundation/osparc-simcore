from datetime import timedelta

from pydantic import AnyHttpUrl, Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


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


if __name__ == "__main__":
    print(LocustSettings().model_dump_json())
