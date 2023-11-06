from functools import cached_property
from typing import cast

from pydantic import Field, PositiveInt, parse_obj_as, validator
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import BuildTargetEnum, LogLevel, VersionTag
from settings_library.director_v2 import DirectorV2Settings
from settings_library.rabbit import RabbitSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME


class _BaseApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    """Base settings of any osparc service's app"""

    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = PROJECT_NAME
    API_VTAG: VersionTag = parse_obj_as(VersionTag, API_VTAG)

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: str | None = None
    SC_BUILD_TARGET: BuildTargetEnum | None = None
    SC_VCS_REF: str | None = None
    SC_VCS_URL: str | None = None

    # @Dockerfile
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

    DYNAMIC_SCHEDULER__LOGLEVEL: LogLevel = Field(
        default=LogLevel.INFO,
        env=["DYNAMIC_SCHEDULER__LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )
    DYNAMIC_SCHEDULER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "DYNAMIC_SCHEDULER__LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )

    @cached_property
    def LOG_LEVEL(self):  # noqa: N802
        return self.DYNAMIC_SCHEDULER__LOGLEVEL

    @validator("DYNAMIC_SCHEDULER__LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))


class ApplicationSettings(_BaseApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    DYNAMIC_SCHEDULER_RABBITMQ: RabbitSettings = Field(
        auto_default_from_env=True, description="settings for service/rabbitmq"
    )

    DYNAMIC_SCHEDULER_SWAGGER_API_DOC_ENABLED: bool = Field(
        default=True, description="If true, it displays swagger doc at /doc"
    )

    DYNAMIC_SCHEDULER_DIRECTOR_V2_SETTINGS: DirectorV2Settings = Field(
        auto_default_from_env=True, description="settings for director-v2 service"
    )
