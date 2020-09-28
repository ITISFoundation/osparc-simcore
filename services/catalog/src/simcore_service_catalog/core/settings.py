import logging
from enum import Enum
from typing import Optional

from pydantic import BaseSettings, Field, SecretStr, validator
from pydantic.types import PositiveInt
from yarl import URL


class BootModeEnum(str, Enum):
    debug = "debug-ptvsd"
    production = "production"
    development = "development"


class _CommonConfig:
    case_sensitive = False
    env_file = ".env"  # SEE https://pydantic-docs.helpmanual.io/usage/settings/#dotenv-env-support


class DirectorSettings(BaseSettings):
    enabled: bool = Field(
        True, description="Enables/Disables connection with director service"
    )
    host: str
    port: int = 8080
    vtag: str = "v0"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/{self.vtag}"

    class Config(_CommonConfig):
        env_prefix = "DIRECTOR_"


class PostgresSettings(BaseSettings):
    enabled: bool = Field(
        True, description="Enables/Disables connection with postgres service"
    )
    user: str
    password: SecretStr
    db: str
    host: str
    port: int = 5432

    minsize: int = 10
    maxsize: int = 10

    @property
    def dsn(self) -> URL:
        return URL.build(
            scheme="postgresql",
            user=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            path=f"/{self.db}",
        )

    class Config(_CommonConfig):
        env_prefix = "POSTGRES_"


class AppSettings(BaseSettings):
    @classmethod
    def create_default(cls) -> "AppSettings":
        # This call triggers parsers
        return cls(postgres=PostgresSettings(), director=DirectorSettings())

    # pylint: disable=no-self-use
    # pylint: disable=no-self-argument

    # DOCKER
    boot_mode: Optional[BootModeEnum] = Field(..., env="SC_BOOT_MODE")

    # LOGGING
    log_level_name: str = Field("DEBUG", env="LOG_LEVEL")

    @validator("log_level_name")
    def match_logging_level(cls, value) -> str:
        try:
            getattr(logging, value.upper())
        except AttributeError as err:
            raise ValueError(f"{value.upper()} is not a valid level") from err
        return value.upper()

    @property
    def loglevel(self) -> int:
        return getattr(logging, self.log_level_name)

    # POSTGRES
    postgres: PostgresSettings

    # DIRECTOR SERVICE
    director: DirectorSettings

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "0.0.0.0"  # nosec
    port: int = 8000
    debug: bool = False  # If True, debug tracebacks should be returned on errors.

    # BACKGROUND TASK
    background_task_rest_time: PositiveInt = 60
    background_task_wait_after_failure: PositiveInt = 5 # secs
    access_rights_default_product_name: str = "osparc"

    class Config(_CommonConfig):
        env_prefix = ""
