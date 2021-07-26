import logging
from enum import Enum
from typing import Optional

from models_library.settings.http_clients import ClientRequestSettings
from models_library.settings.postgres import PostgresSettings
from pydantic import BaseSettings, Field, validator
from pydantic.types import PositiveInt

logger = logging.getLogger(__name__)


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


class AppSettings(BaseSettings):
    @classmethod
    def create_default(cls) -> "AppSettings":
        # This call triggers parsers
        return cls(
            postgres=PGSettings(),
            director=DirectorSettings(),
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

    # fastappi app settings
    debug: bool = False  # If True, debug tracebacks should be returned on errors.

    # BACKGROUND TASK
    background_task_rest_time: PositiveInt = 60
    background_task_wait_after_failure: PositiveInt = 5  # secs
    access_rights_default_product_name: str = "osparc"

    CATALOG_DEV_FEATURES_ENABLED: bool = Field(
        False,
        description="Enables development features. WARNING: make sure it is disabled in production .env file!",
    )

    @validator("CATALOG_DEV_FEATURES_ENABLED")
    def _warn_dev_features_enabled(cls, v):
        if v:
            logger.warning("Development features are ENABLED")
        return v

    class Config(_CommonConfig):
        env_prefix = ""
