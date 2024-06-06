from functools import cached_property
from typing import Final, cast

from fastapi import FastAPI
from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    VersionTag,
)
from pydantic import Field, PositiveInt, validator
from settings_library.base import BaseCustomSettings
from settings_library.efs import AwsEfsSettings
from settings_library.rabbit import RabbitSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, APP_NAME

EFS_GUARDIAN_ENV_PREFIX: Final[str] = "EFS_GUARDIAN_"


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: str | None = None
    SC_BUILD_TARGET: BuildTargetEnum | None = None
    SC_VCS_REF: str | None = None
    SC_VCS_URL: str | None = None

    # @Dockerfile
    SC_BOOT_MODE: BootModeEnum | None = None
    SC_BOOT_TARGET: BuildTargetEnum | None = None
    SC_HEALTHCHECK_TIMEOUT: PositiveInt | None = Field(
        None,
        description="If a single run of the check takes longer than timeout seconds "
        "then the check is considered to have failed."
        "It takes retries consecutive failures of the health check for the container to be considered unhealthy.",
    )
    SC_USER_ID: int | None = None
    SC_USER_NAME: str | None = None

    # RUNTIME  -----------------------------------------------------------
    EFS_GUARDIAN_DEBUG: bool = Field(
        default=False, description="Debug mode", env=["EFS_GUARDIAN_DEBUG", "DEBUG"]
    )
    EFS_GUARDIAN_LOGLEVEL: LogLevel = Field(
        LogLevel.INFO, env=["EFS_GUARDIAN_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )
    EFS_GUARDIAN_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "EFS_GUARDIAN_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )

    EFS_GUARDIAN_AWS_EFS_SETTINGS: AwsEfsSettings = Field(auto_default_from_env=True)
    EFS_GUARDIAN_RABBITMQ: RabbitSettings = Field(auto_default_from_env=True)

    @cached_property
    def LOG_LEVEL(self) -> LogLevel:  # noqa: N802
        return self.EFS_GUARDIAN_LOGLEVEL

    @validator("EFS_GUARDIAN_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    return cast(ApplicationSettings, app.state.settings)
