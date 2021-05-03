import logging
from enum import Enum
from typing import Optional

from models_library.settings.http_clients import ClientRequestSettings
from pydantic import BaseSettings, Field, validator


class BootModeEnum(str, Enum):
    DEBUG = "debug-ptvsd"
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class _CommonConfig:
    case_sensitive = False
    env_file = ".env"


# SERVICES CLIENTS --------------------------------------------
class BaseServiceSettings(BaseSettings):
    enabled: bool = Field(True, description="Enables/Disables connection with service")
    host: str
    port: int = 8080
    vtag: str = "v0"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/{self.vtag}"


# MAIN SETTINGS --------------------------------------------


class AppSettings(BaseSettings):
    @classmethod
    def create_from_env(cls) -> "AppSettings":
        # This call triggers parsers
        return cls(
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
            return value.upper()
        except AttributeError as err:
            raise ValueError(f"{value.upper()} is not a valid level") from err

    @property
    def loglevel(self) -> int:
        return getattr(logging, self.log_level_name)

    # SERVICES with http API
    client_request: ClientRequestSettings

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "0.0.0.0"  # nosec
    port: int = 8000

    debug: bool = False  # If True, debug tracebacks should be returned on errors.
    remote_debug_port: int = 3000
    dev_features_enabled: bool = Field(
        False,
        env=[
            "comp_resource_manager_DEV_FEATURES_ENABLED",
            "FAKE_comp_resource_manager_ENABLED",
        ],
    )

    class Config(_CommonConfig):
        env_prefix = ""
