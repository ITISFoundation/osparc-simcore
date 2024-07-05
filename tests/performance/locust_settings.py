from pydantic import AnyHttpUrl, Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True)

    LOCUST_HOST: AnyHttpUrl = Field(
        default=..., examples=["https://api.osparc-master.speag.com"]
    )
    LOCUST_USERS: PositiveInt = Field(default=...)
    LOCUST_HEADLESS: str = Field(default=...)
    LOCUST_PRINT_STATS: str = Field(default=...)
    LOCUST_SPAWN_RATE: PositiveInt = Field(default=...)
    LOCUST_RUN_TIME: str = Field(default=...)


if __name__ == "__main__":
    settings = Settings()
    env_vars = [f"{key}={value}" for key, value in settings.model_dump().items()]
    print("\n".join(env_vars))
