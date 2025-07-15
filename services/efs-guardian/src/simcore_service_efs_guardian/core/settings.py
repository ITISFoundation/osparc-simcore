import datetime
from functools import cached_property
from typing import Annotated, Final, cast

from common_library.basic_types import DEFAULT_FACTORY
from fastapi import FastAPI
from models_library.basic_types import LogLevel, VersionTag
from pydantic import AliasChoices, ByteSize, Field, TypeAdapter, field_validator
from servicelib.logging_utils import LogLevelInt
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.application import BaseApplicationSettings
from settings_library.efs import AwsEfsSettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, APP_NAME

EFS_GUARDIAN_ENV_PREFIX: Final[str] = "EFS_GUARDIAN_"


class ApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    EFS_USER_ID: Annotated[
        int, Field(description="Linux user ID that the Guardian service will run with")
    ]
    EFS_USER_NAME: Annotated[
        str,
        Field(description="Linux user name that the Guardian service will run with"),
    ]
    EFS_GROUP_ID: Annotated[
        int,
        Field(
            description="Linux group ID that the EFS and Simcore linux users are part of"
        ),
    ]
    EFS_GROUP_NAME: Annotated[
        str,
        Field(
            description="Linux group name that the EFS and Simcore linux users are part of"
        ),
    ]
    EFS_DEFAULT_USER_SERVICE_SIZE_BYTES: ByteSize = TypeAdapter(
        ByteSize
    ).validate_python("500GiB")

    EFS_REMOVAL_POLICY_TASK_AGE_LIMIT_TIMEDELTA: Annotated[
        datetime.timedelta,
        Field(
            description="For how long must a project remain unused before we remove its data from the EFS. (default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
        ),
    ] = datetime.timedelta(days=10)

    # RUNTIME  -----------------------------------------------------------
    EFS_GUARDIAN_DEBUG: Annotated[
        bool,
        Field(
            description="Debug mode",
            validation_alias=AliasChoices("EFS_GUARDIAN_DEBUG", "DEBUG"),
        ),
    ] = False

    EFS_GUARDIAN_LOGLEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices(
                "EFS_GUARDIAN_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"
            ),
        ),
    ] = LogLevel.INFO

    EFS_GUARDIAN_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "EFS_GUARDIAN_LOG_FORMAT_LOCAL_DEV_ENABLED",
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
        ),
    ] = False
    EFS_GUARDIAN_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices(
                "EFS_GUARDIAN_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
            ),
            description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
        ),
    ] = DEFAULT_FACTORY

    EFS_GUARDIAN_AWS_EFS_SETTINGS: Annotated[
        AwsEfsSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    EFS_GUARDIAN_POSTGRES: Annotated[
        PostgresSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    EFS_GUARDIAN_RABBITMQ: Annotated[
        RabbitSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    EFS_GUARDIAN_REDIS: Annotated[
        RedisSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    EFS_GUARDIAN_TRACING: Annotated[
        TracingSettings | None,
        Field(
            description="settings for opentelemetry tracing",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    @cached_property
    def log_level(self) -> LogLevelInt:
        return cast(LogLevelInt, self.EFS_GUARDIAN_LOGLEVEL)

    @field_validator("EFS_GUARDIAN_LOGLEVEL", mode="before")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    return cast(ApplicationSettings, app.state.settings)
