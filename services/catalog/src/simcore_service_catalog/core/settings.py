import logging
from enum import Enum
from typing import Optional

from pydantic import BaseSettings, Field, SecretStr, validator
from yarl import URL


class BootModeEnum(str, Enum):
    debug = "debug-ptvsd"
    production = "production"
    development = "development"


class _CommonConfig:
    case_sensitive = False
    env_file = ".env"  # SEE https://pydantic-docs.helpmanual.io/usage/settings/#dotenv-env-support


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
        return cls(postgres=PostgresSettings())

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
        except AttributeError:
            raise ValueError(f"{value.upper()} is not a valid level")
        return value.upper()

    @property
    def loglevel(self) -> int:
        return getattr(logging, self.log_level_name)

    # POSTGRES
    postgres: PostgresSettings

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "0.0.0.0"  # nosec
    port: int = 8000
    debug: bool = False  # If True, debug tracebacks should be returned on errors.

    class Config(_CommonConfig):
        env_prefix = ""
