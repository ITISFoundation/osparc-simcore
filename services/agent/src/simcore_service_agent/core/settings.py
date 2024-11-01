from datetime import timedelta

from models_library.basic_types import BootModeEnum, LogLevel
from pydantic import AnyHttpUrl, Field, validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.r_clone import S3Provider
from settings_library.rabbit import RabbitSettings
from settings_library.utils_logging import MixinLoggingSettings


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    LOGLEVEL: LogLevel = Field(
        LogLevel.WARNING.value, env=["AGENT_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )
    SC_BOOT_MODE: BootModeEnum | None

    AGENT_VOLUMES_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "AGENT_VOLUMES_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description=(
            "Enables local development log format. WARNING: make sure it is "
            "disabled if you want to have structured logs!"
        ),
    )
    AGENT_VOLUMES_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        env=["AGENT_VOLUMES_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"],
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )
    AGENT_VOLUMES_CLEANUP_TARGET_SWARM_STACK_NAME: str = Field(
        ..., description="Exactly the same as director-v2's `SWARM_STACK_NAME` env var"
    )
    AGENT_VOLUMES_CLEANUP_S3_ENDPOINT: AnyHttpUrl
    AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY: str
    AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY: str
    AGENT_VOLUMES_CLEANUP_S3_BUCKET: str
    AGENT_VOLUMES_CLEANUP_S3_PROVIDER: S3Provider
    AGENT_VOLUMES_CLEANUP_S3_REGION: str = "us-east-1"
    AGENT_VOLUMES_CLEANUP_RETRIES: int = Field(
        3, description="upload retries in case of error"
    )
    AGENT_VOLUMES_CLEANUP_PARALLELISM: int = Field(
        5, description="parallel transfers to s3"
    )
    AGENT_VOLUMES_CLEANUP_EXCLUDE_FILES: list[str] = Field(
        [".hidden_do_not_remove", "key_values.json"],
        description="Files to ignore when syncing to s3",
    )
    AGENT_VOLUMES_CLEANUP_INTERVAL: timedelta = Field(
        timedelta(minutes=1), description="interval for running volumes removal"
    )
    AGENT_VOLUMES_CLENUP_BOOK_KEEPING_INTERVAL: timedelta = Field(
        timedelta(minutes=1),
        description=(
            "interval at which to scan for unsued volumes and keep track since "
            "they were detected as being unused"
        ),
    )
    AGENT_VOLUMES_CLENUP_REMOVE_VOLUMES_INACTIVE_FOR: timedelta = Field(
        timedelta(minutes=65),
        description=(
            "if a volume is unused for more than this interval it can be removed. "
            "The default is set to a health 60+ miunutes since it might take upto "
            "60 minutes for the dy-sidecar to properly save data form the volumes"
        ),
    )

    AGENT_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True

    AGENT_DOCKER_NODE_ID: str = Field(..., description="used by the rabbitmq module")

    AGENT_RABBITMQ: RabbitSettings = Field(
        auto_default_from_env=True, description="settings for service/rabbitmq"
    )

    @validator("LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value) -> LogLevel:
        return LogLevel(cls.validate_log_level(value))
