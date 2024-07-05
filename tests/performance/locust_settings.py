from pydantic import AnyHttpUrl, Field, PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LocustSettings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True)

    LOCUST_HOST: AnyHttpUrl = Field(
        default=..., examples=["https://api.osparc-master.speag.com"]
    )
    LOCUST_USERS: PositiveInt = Field(default=...)
    LOCUST_HEADLESS: str = Field(default="true")
    LOCUST_PRINT_STATS: str = Field(default="true")
    LOCUST_SPAWN_RATE: PositiveInt = Field(default=20)
    LOCUST_RUN_TIME: str = Field(default="1m")

    @field_validator("LOCUST_HEADLESS", mode="after")
    @classmethod
    def ensure_bool(cls, v: str):
        if not v in {"true", "false"}:
            raise ValueError("Only 'true' or 'false' is allowed")


if __name__ == "__main__":
    settings = LocustSettings()
    env_vars = [f"{key}={value}" for key, value in settings.model_dump().items()]
    print("\n".join(env_vars))
