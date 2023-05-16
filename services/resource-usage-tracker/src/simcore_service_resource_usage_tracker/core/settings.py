from functools import cached_property
from typing import cast

from models_library.basic_types import BootModeEnum
from pydantic import Field, HttpUrl, PositiveInt, validator
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import BuildTargetEnum, LogLevel, VersionTag
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME


class _BaseApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = PROJECT_NAME
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
        default=None,
        description="If a single run of the check takes longer than timeout seconds "
        "then the check is considered to have failed."
        "It takes retries consecutive failures of the health check for the container to be considered unhealthy.",
    )
    SC_USER_ID: int | None = None
    SC_USER_NAME: str | None = None

    # RUNTIME  -----------------------------------------------------------
    RESOURCE_USAGE_TRACKER_DEBUG: bool = Field(
        False, description="Debug mode", env=["RESOURCE_USAGE_TRACKER_DEBUG", "DEBUG"]
    )
    RESOURCE_USAGE_TRACKER_LOGLEVEL: LogLevel = Field(
        default=LogLevel.INFO,
        env=["RESOURCE_USAGE_TRACKER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )
    RESOURCE_USAGE_TRACKER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        False,
        env=[
            "RESOURCE_USAGE_TRACKER_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )

    @cached_property
    def LOG_LEVEL(self) -> LogLevel:
        return self.RESOURCE_USAGE_TRACKER_LOGLEVEL

    @validator("RESOURCE_USAGE_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))


class MinimalApplicationSettings(_BaseApplicationSettings):
    """Extends base settings with the settings needed to create invitation links

    Separated for convenience to run some commands of the CLI that
    are not related to the web server.
    """

    RESOURCE_USAGE_TRACKER_PROMETHEUS_URL: HttpUrl = Field(
        ..., description="Prometheus URL"
    )


class ApplicationSettings(MinimalApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    RESOURCE_USAGE_TRACKER_EVALUATION_INTERVAL_SEC: int = Field(
        default=300, description="Interval in seconds to evaluate the resource usage"
    )
    RESOURCE_USAGE_TRACKER_GRANULARITY_SEC: int = Field(
        default=60,
        description="Granularity to fetch data from prometheus. This should be larger than prometheus scraping interval.",
    )
    RESOURCE_USAGE_TRACKER_CONTAINER_LABEL_USER_ID_REGEX: str = Field(
        default=".*",
        # regex=r"^(([_a-zA-Z0-9:.-]+)/)?(dynamic-sidecar):([_a-zA-Z0-9.-]+)$",
        description="Regex for the prometheus timeseries label `CONTAINER_LABEL_USER_ID`.",
    )
    RESOURCE_USAGE_TRACKER_PROMETHEUS_USERNAME: str | None = Field(
        default=None, description="Username to access the prometheus server"
    )
    RESOURCE_USAGE_TRACKER_PROMETHEUS_PASSWORD: str | None = Field(
        default=None, description="Password to access the prometheus server"
    )
