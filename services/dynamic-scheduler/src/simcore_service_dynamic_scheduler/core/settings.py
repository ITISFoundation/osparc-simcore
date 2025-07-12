import datetime
from functools import cached_property
from typing import Annotated, cast

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import AliasChoices, Field, SecretStr, TypeAdapter, field_validator
from servicelib.logging_utils import LogLevelInt
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.application import BaseApplicationSettings
from settings_library.basic_types import LogLevel, VersionTag
from settings_library.catalog import CatalogSettings
from settings_library.director_v0 import DirectorV0Settings
from settings_library.director_v2 import DirectorV2Settings
from settings_library.docker_api_proxy import DockerApiProxysettings
from settings_library.http_client_request import ClientRequestSettings
from settings_library.postgres import PostgresSettings
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
    API_VTAG: VersionTag = TypeAdapter(VersionTag).validate_python(API_VTAG)

    # RUNTIME  -----------------------------------------------------------

    DYNAMIC_SCHEDULER_LOGLEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices(
                "DYNAMIC_SCHEDULER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"
            ),
        ),
    ] = LogLevel.INFO

    DYNAMIC_SCHEDULER_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
                "DYNAMIC_SCHEDULER_LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description=(
                "Enables local development log format. WARNING: make sure it "
                "is disabled if you want to have structured logs!"
            ),
        ),
    ] = False

    DYNAMIC_SCHEDULER_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices(
                "LOG_FILTER_MAPPING",
                "DYNAMIC_SCHEDULER_LOG_FILTER_MAPPING",
            ),
            description=(
                "is a dictionary that maps specific loggers "
                "(such as 'uvicorn.access' or 'gunicorn.access') to a list "
                "of log message patterns that should be filtered out."
            ),
        ),
    ] = DEFAULT_FACTORY

    DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT: Annotated[
        datetime.timedelta,
        Field(
            validation_alias=AliasChoices(
                "DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT",
                "DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT",
            ),
            description=(
                "Time to wait before timing out when stopping a dynamic service. "
                "Since services require data to be stopped, this operation is timed out after 1 hour"
            ),
        ),
    ] = datetime.timedelta(minutes=60)

    DYNAMIC_SCHEDULER_SERVICE_UPLOAD_DOWNLOAD_TIMEOUT: Annotated[
        datetime.timedelta,
        Field(
            description=(
                "When dynamic services upload and download data from storage, "
                "sometimes very big payloads are involved. In order to handle "
                "such payloads it is required to have long timeouts which "
                "allow the service to finish the operation."
            ),
        ),
    ] = datetime.timedelta(minutes=60)

    DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER: Annotated[
        bool,
        Field(
            description=(
                "this is a way to switch between different dynamic schedulers for the new style services"
                # NOTE: this option should be removed when the scheduling will be done via this service
            ),
        ),
    ] = False

    @cached_property
    def log_level(self) -> LogLevelInt:
        return cast(LogLevelInt, self.DYNAMIC_SCHEDULER_LOGLEVEL)

    @field_validator("DYNAMIC_SCHEDULER_LOGLEVEL", mode="before")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


class ApplicationSettings(_BaseApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    DYNAMIC_SCHEDULER_UI_STORAGE_SECRET: SecretStr = Field(
        ...,
        description=(
            "secret required to enabled browser-based storage for the UI. "
            "Enables the full set of features to be used for NiceUI"
        ),
    )

    DYNAMIC_SCHEDULER_UI_MOUNT_PATH: Annotated[
        str, Field(description="path on the URL where the dashboard is mounted")
    ] = "/dynamic-scheduler/"

    DYNAMIC_SCHEDULER_RABBITMQ: RabbitSettings = Field(
        json_schema_extra={"auto_default_from_env": True},
        description="settings for service/rabbitmq",
    )

    DYNAMIC_SCHEDULER_REDIS: RedisSettings = Field(
        json_schema_extra={"auto_default_from_env": True},
        description="settings for service/redis",
    )

    DYNAMIC_SCHEDULER_SWAGGER_API_DOC_ENABLED: Annotated[
        bool, Field(description="If true, it displays swagger doc at /doc")
    ] = True

    CLIENT_REQUEST: ClientRequestSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    DYNAMIC_SCHEDULER_DIRECTOR_V0_SETTINGS: DirectorV0Settings = Field(
        json_schema_extra={"auto_default_from_env": True},
        description="settings for director service",
    )

    DYNAMIC_SCHEDULER_DIRECTOR_V2_SETTINGS: DirectorV2Settings = Field(
        json_schema_extra={"auto_default_from_env": True},
        description="settings for director-v2 service",
    )

    DYNAMIC_SCHEDULER_CATALOG_SETTINGS: CatalogSettings = Field(
        json_schema_extra={"auto_default_from_env": True},
        description="settings for catalog service",
    )

    DYNAMIC_SCHEDULER_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True

    DYNAMIC_SCHEDULER_PROFILING: bool = False

    DYNAMIC_SCHEDULER_TRACING: TracingSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True},
        description="settings for opentelemetry tracing",
    )

    DYNAMIC_SCHEDULER_DOCKER_API_PROXY: Annotated[
        DockerApiProxysettings,
        Field(json_schema_extra={"auto_default_from_env": True}),
    ]

    DYNAMIC_SCHEDULER_POSTGRES: Annotated[
        PostgresSettings,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="settings for postgres service",
        ),
    ]

    @field_validator("DYNAMIC_SCHEDULER_UI_MOUNT_PATH", mode="before")
    @classmethod
    def _ensure_ends_with_slash(cls, v: str) -> str:
        if not v.endswith("/"):
            msg = f"Provided mount path: '{v}' must be '/' terminated"
            raise ValueError(msg)
        return v
