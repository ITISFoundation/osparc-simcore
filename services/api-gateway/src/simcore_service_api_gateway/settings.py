# pylint: disable=no-name-in-module

from pydantic import BaseSettings, Field, SecretStr, validator
from enum import Enum
from typing import Optional
from yarl import URL
import logging

class BootModeEnum(str, Enum):
    production = "production"
    development = "development"


class Settings(BaseSettings):
    #pylint: disable=no-self-use
    #pylint: disable=no-self-argument

    # DOCKER
    boot_mode: Optional[BootModeEnum] = Field(None, env="SC_BOOT_MODE")

    # LOGGING
    log_level_name: str = Field("DEBUG", env="loglevel")

    @validator('loglevel_name')
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
            path=f"/{self.postgres_db}"
        )

    # WEBSERVER
    webserver_host: str = "webserver"
    webserver_port: int = 8080

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "localhost"  # "0.0.0.0" if is_containerized else "127.0.0.1",
    port: int = 8000

    class Config:
        env_prefix = ""
        case_sensitive = False
