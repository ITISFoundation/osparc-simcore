import datetime
from functools import cached_property
from typing import Final, cast

from fastapi import FastAPI
from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    VersionTag,
)
from pydantic import (
    AliasChoices,
    ByteSize,
    Field,
    PositiveInt,
    TypeAdapter,
    field_validator,
)
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.efs import AwsEfsSettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.tracing import TracingSettings
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
    SC_USER_ID: int
    SC_USER_NAME: str

    EFS_USER_ID: int = Field(
        description="Linux user ID that the Guardian service will run with"
    )
    EFS_USER_NAME: str = Field(
        description="Linux user name that the Guardian service will run with"
    )
    EFS_GROUP_ID: int = Field(
        description="Linux group ID that the EFS and Simcore linux users are part of"
    )
    EFS_GROUP_NAME: str = Field(
        description="Linux group name that the EFS and Simcore linux users are part of"
    )
    EFS_DEFAULT_USER_SERVICE_SIZE_BYTES: ByteSize = Field(
        default=TypeAdapter(ByteSize).validate_python("500GiB")
    )
    EFS_REMOVAL_POLICY_TASK_AGE_LIMIT_TIMEDELTA: datetime.timedelta = Field(
        default=datetime.timedelta(days=10),
        description="For how long must a project remain unused before we remove its data from the EFS. (default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )

    # RUNTIME  -----------------------------------------------------------
    EFS_GUARDIAN_DEBUG: bool = Field(
        default=False,
        description="Debug mode",
        validation_alias=AliasChoices("EFS_GUARDIAN_DEBUG", "DEBUG"),
    )
    EFS_GUARDIAN_LOGLEVEL: LogLevel = Field(
        LogLevel.INFO,
        validation_alias=AliasChoices("EFS_GUARDIAN_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"),
    )
    EFS_GUARDIAN_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "EFS_GUARDIAN_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ),
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    EFS_GUARDIAN_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "EFS_GUARDIAN_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
        ),
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )

    EFS_GUARDIAN_AWS_EFS_SETTINGS: AwsEfsSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    EFS_GUARDIAN_POSTGRES: PostgresSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    EFS_GUARDIAN_RABBITMQ: RabbitSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    EFS_GUARDIAN_REDIS: RedisSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    EFS_GUARDIAN_TRACING: TracingSettings | None = Field(
        description="settings for opentelemetry tracing",
        json_schema_extra={"auto_default_from_env": True},
    )

    @cached_property
    def LOG_LEVEL(self) -> LogLevel:  # noqa: N802
        return self.EFS_GUARDIAN_LOGLEVEL

    @field_validator("EFS_GUARDIAN_LOGLEVEL", mode="before")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    return cast(ApplicationSettings, app.state.settings)
