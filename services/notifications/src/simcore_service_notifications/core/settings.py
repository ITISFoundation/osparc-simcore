from typing import Annotated

from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from models_library.basic_types import BootModeEnum, LogLevel
from pydantic import AliasChoices, Field, field_validator
from settings_library.application import BaseApplicationSettings
from settings_library.celery import CelerySettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings


class ApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    LOG_LEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices(
                "NOTIFICATIONS_LOGLEVEL",
                "LOG_LEVEL",
                "LOGLEVEL",
            ),
        ),
    ] = LogLevel.WARNING

    SC_BOOT_MODE: BootModeEnum | None

    NOTIFICATIONS_CELERY: Annotated[
        CelerySettings | None,
        Field(
            description="Settings for Celery",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    NOTIFICATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "NOTIFICATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED",
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description=(
                "Enables local development log format. WARNING: make sure it is "
                "disabled if you want to have structured logs!"
            ),
        ),
    ] = False

    NOTIFICATIONS_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices(
                "NOTIFICATIONS_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
            ),
            description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
        ),
    ] = DEFAULT_FACTORY

    NOTIFICATIONS_RABBITMQ: Annotated[
        RabbitSettings,
        Field(
            description="settings for service/rabbitmq",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    NOTIFICATIONS_POSTGRES: Annotated[
        PostgresSettings,
        Field(
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    NOTIFICATIONS_TRACING: Annotated[
        TracingSettings | None,
        Field(
            description="settings for opentelemetry tracing",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    NOTIFICATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True

    NOTIFICATIONS_WORKER_MODE: Annotated[
        bool, Field(description="If True, run as a worker")
    ] = False

    @field_validator("LOG_LEVEL")
    @classmethod
    def valid_log_level(cls, value) -> LogLevel:
        return LogLevel(cls.validate_log_level(value))
