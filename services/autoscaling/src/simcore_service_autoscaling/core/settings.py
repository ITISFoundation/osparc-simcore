from functools import cached_property
from typing import Optional

from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    VersionTag,
)
from pydantic import Field, PositiveInt, validator
from settings_library.base import BaseCustomSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, APP_NAME


class AwsSettings(BaseCustomSettings):
    AWS_KEY_NAME: str
    AWS_DNS: str
    AWS_ACCESS_KEY_ID: str
    AWS_REGION_NAME: str = "us-east-1"
    AWS_SECRET_ACCESS_KEY: str
    AWS_SECURITY_GROUP_IDS: list[str]
    AWS_SUBNET_ID: str


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: Optional[str] = None
    SC_BUILD_TARGET: Optional[BuildTargetEnum] = None
    SC_VCS_REF: Optional[str] = None
    SC_VCS_URL: Optional[str] = None

    # @Dockerfile
    SC_BOOT_MODE: Optional[BootModeEnum] = None
    SC_BOOT_TARGET: Optional[BuildTargetEnum] = None
    SC_HEALTHCHECK_TIMEOUT: Optional[PositiveInt] = Field(
        None,
        description="If a single run of the check takes longer than timeout seconds "
        "then the check is considered to have failed."
        "It takes retries consecutive failures of the health check for the container to be considered unhealthy.",
    )
    SC_USER_ID: Optional[int] = None
    SC_USER_NAME: Optional[str] = None

    # RUNTIME  -----------------------------------------------------------
    AUTOSCALING_DEBUG: bool = Field(
        False, description="Debug mode", env=["AUTOSCALING_DEBUG", "DEBUG"]
    )

    AUTOSCALING_LOGLEVEL: LogLevel = Field(
        LogLevel.INFO, env=["AUTOSCALING_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )

    @cached_property
    def LOG_LEVEL(self):
        return self.AUTOSCALING_LOGLEVEL

    AUTOSCALING_AWS: Optional[AwsSettings] = Field(auto_default_from_env=True)

    @validator("AUTOSCALING_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value) -> str:
        return cls.validate_log_level(value)
