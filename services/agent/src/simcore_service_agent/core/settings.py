from datetime import timedelta
from typing import Annotated

from common_library.basic_types import DEFAULT_FACTORY
from models_library.basic_types import BootModeEnum, LogLevel
from models_library.docker import DockerNodeID
from pydantic import AliasChoices, AnyHttpUrl, Field, field_validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.r_clone import S3Provider
from settings_library.rabbit import RabbitSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    LOG_LEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices(
                "AGENT_LOGLEVEL",
                "LOG_LEVEL",
                "LOGLEVEL",
            ),
        ),
    ] = LogLevel.WARNING

    SC_BOOT_MODE: BootModeEnum | None

    AGENT_VOLUMES_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "AGENT_VOLUMES_LOG_FORMAT_LOCAL_DEV_ENABLED",
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description=(
                "Enables local development log format. WARNING: make sure it is "
                "disabled if you want to have structured logs!"
            ),
        ),
    ] = False

    AGENT_VOLUMES_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices(
                "AGENT_VOLUMES_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
            ),
            description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
        ),
    ] = DEFAULT_FACTORY

    AGENT_VOLUMES_CLEANUP_TARGET_SWARM_STACK_NAME: str
    AGENT_VOLUMES_CLEANUP_S3_ENDPOINT: AnyHttpUrl
    AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY: str
    AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY: str
    AGENT_VOLUMES_CLEANUP_S3_BUCKET: str
    AGENT_VOLUMES_CLEANUP_S3_PROVIDER: S3Provider
    AGENT_VOLUMES_CLEANUP_S3_REGION: str = "us-east-1"
    AGENT_VOLUMES_CLEANUP_RETRIES: Annotated[
        int, Field(description="upload retries in case of error")
    ] = 3
    AGENT_VOLUMES_CLEANUP_PARALLELISM: Annotated[
        int, Field(description="parallel transfers to s3")
    ] = 5
    AGENT_VOLUMES_CLEANUP_EXCLUDE_FILES: Annotated[
        list[str],
        Field(
            [".hidden_do_not_remove", "key_values.json"],
            description="Files to ignore when syncing to s3",
        ),
    ]
    AGENT_VOLUMES_CLEANUP_INTERVAL: Annotated[
        timedelta, Field(description="interval for running volumes removal")
    ] = timedelta(minutes=1)
    AGENT_VOLUMES_CLEANUP_BOOK_KEEPING_INTERVAL: Annotated[
        timedelta,
        Field(
            description=(
                "interval at which to scan for unsued volumes and keep track since "
                "they were detected as being unused"
            ),
        ),
    ] = timedelta(minutes=1)
    AGENT_VOLUMES_CLEANUP_REMOVE_VOLUMES_INACTIVE_FOR: Annotated[
        timedelta,
        Field(
            description=(
                "if a volume is unused for more than this interval it can be removed. "
                "The default is set to a health 60+ miunutes since it might take upto "
                "60 minutes for the dy-sidecar to properly save data form the volumes"
            ),
        ),
    ] = timedelta(minutes=65)

    AGENT_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True
    AGENT_DOCKER_NODE_ID: Annotated[
        DockerNodeID, Field(description="used by the rabbitmq module")
    ]

    AGENT_RABBITMQ: Annotated[
        RabbitSettings,
        Field(
            description="settings for service/rabbitmq",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    AGENT_TRACING: Annotated[
        TracingSettings | None,
        Field(
            description="settings for opentelemetry tracing",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    @field_validator("LOG_LEVEL")
    @classmethod
    def valid_log_level(cls, value) -> LogLevel:
        return LogLevel(cls.validate_log_level(value))
