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
    env_file = ".env"


class WebServerSettings(BaseSettings):
    enabled: bool = Field(
        True, description="Enables/Disables connection with webserver service"
    )
    host: str = "webserver"
    port: int = 8080
    session_secret_key: SecretStr
    session_name: str = "osparc.WEBAPI_SESSION"
    vtag: str = "v0"

    class Config(_CommonConfig):
        env_prefix = "WEBSERVER_"

    @property
    def base_url(self):
        return f"http://{self.host}:{self.port}/{self.vtag}"


class AppSettings(BaseSettings):
    # pylint: disable=no-self-use
    # pylint: disable=no-self-argument

    # DOCKER
    boot_mode: Optional[BootModeEnum] = Field(None, env="SC_BOOT_MODE")

    # LOGGING
    log_level_name: str = Field("DEBUG", env="loglevel")

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
    postgres_enabled: bool = Field(
        True, description="Enables/Disables connection with postgres service"
    )
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def postgres_dsn(self) -> URL:
        return URL.build(
            scheme="postgresql",
            user=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            path=f"/{self.postgres_db}",
        )

    # WEB-SERVER SERVICE
    webserver = WebServerSettings()

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "localhost"  # "0.0.0.0" if is_containerized else "127.0.0.1",
    port: int = 8000

    debug: bool = False  # If True, debug tracebacks should be returned on errors.

    class Config(_CommonConfig):
        env_prefix = ""
