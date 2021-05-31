import logging
from enum import Enum
from typing import Optional

from models_library.settings.http_clients import ClientRequestSettings
from models_library.settings.postgres import PostgresSettings
from pydantic import BaseSettings, Field, validator
from pydantic.types import PositiveInt


class BootModeEnum(str, Enum):
    DEBUG = "debug-ptvsd"
    PRODUCTION = "production"
    DEVELOPMENT = "development"


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


class PGSettings(PostgresSettings):
    enabled: bool = Field(True, description="Enables/Disables connection with service")

    class Config(_CommonConfig, PostgresSettings.Config):
        env_prefix = "POSTGRES_"


class RegistrySettings(BaseSettings):
    url: str = Field(..., description="URL to the docker registry")
    ssl: bool = Field(..., description="if registry is secore or not")

    threadpool_max_workers: int = Field(
        None,
        description="Amount of threads to put in the pool, if None uses threadpool's default",
    )

    @property
    def address(self) -> str:
        protocol = "https" if self.ssl else "http"
        return f"{protocol}://{self.url}"

    class Config(_CommonConfig):
        env_prefix = "REGISTRY_"


class AppSettings(BaseSettings):
    @classmethod
    def create_default(cls) -> "AppSettings":
        # This call triggers parsers
        return cls(
            postgres=PGSettings(),
            director=DirectorSettings(),
            registry=RegistrySettings(),
            client_request=ClientRequestSettings(),
        )

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
    postgres: PGSettings

    client_request: ClientRequestSettings

    # DIRECTOR SERVICE
    director: DirectorSettings

    # Docker Registry
    registry: RegistrySettings

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "0.0.0.0"  # nosec
    port: int = 8000
    # fastappi app settings
    debug: bool = False  # If True, debug tracebacks should be returned on errors.

    # BACKGROUND TASK
    background_task_enabled: bool = True
    background_task_rest_time: PositiveInt = 60
    background_task_wait_after_failure: PositiveInt = 5  # secs
    access_rights_default_product_name: str = "osparc"

    class Config(_CommonConfig):
        env_prefix = ""
