import datetime

from pydantic import Field, parse_obj_as, validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.application import BaseApplicationSettings
from settings_library.basic_types import LogLevel, VersionTag
from settings_library.director_v2 import DirectorV2Settings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME


class _BaseApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    """Base settings of any osparc service's app"""

    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = PROJECT_NAME
    API_VTAG: VersionTag = parse_obj_as(VersionTag, API_VTAG)

    # RUNTIME  -----------------------------------------------------------

    DYNAMIC_SCHEDULER_LOGLEVEL: LogLevel = Field(
        default=LogLevel.INFO,
        env=["DYNAMIC_SCHEDULER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )
    DYNAMIC_SCHEDULER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "DYNAMIC_SCHEDULER_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    DYNAMIC_SCHEDULER_LOG_FILTER_MAPPING: dict[
        LoggerName, list[MessageSubstring]
    ] = Field(
        default_factory=dict,
        env=["DYNAMIC_SCHEDULER_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"],
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )

    DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=60),
        description=(
            "Time to wait before timing out when stopping a dynamic service. "
            "Since services require data to be stopped, this operation is timed out after 1 hour"
        ),
    )

    @validator("DYNAMIC_SCHEDULER_LOGLEVEL", pre=True)
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


class ApplicationSettings(_BaseApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    DYNAMIC_SCHEDULER_RABBITMQ: RabbitSettings = Field(
        auto_default_from_env=True, description="settings for service/rabbitmq"
    )

    DYNAMIC_SCHEDULER_REDIS: RedisSettings = Field(
        auto_default_from_env=True, description="settings for service/redis"
    )

    DYNAMIC_SCHEDULER_SWAGGER_API_DOC_ENABLED: bool = Field(
        default=True, description="If true, it displays swagger doc at /doc"
    )

    DYNAMIC_SCHEDULER_DIRECTOR_V2_SETTINGS: DirectorV2Settings = Field(
        auto_default_from_env=True, description="settings for director-v2 service"
    )

    DYNAMIC_SCHEDULER_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True

    DYNAMIC_SCHEDULER_PROFILING: bool = False
    DYNAMIC_SCHEDULER_TRACING: TracingSettings | None = Field(
        auto_default_from_env=True, description="settings for opentelemetry tracing"
    )
