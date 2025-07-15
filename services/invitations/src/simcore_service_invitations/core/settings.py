from functools import cached_property
from typing import Annotated, cast

from common_library.basic_types import DEFAULT_FACTORY
from models_library.products import ProductName
from pydantic import AliasChoices, Field, HttpUrl, SecretStr, field_validator
from servicelib.logging_utils import LogLevelInt
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.application import BaseApplicationSettings
from settings_library.basic_types import LogLevel, VersionTag
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME


class _BaseApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    """Base settings of any osparc service's app"""

    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = PROJECT_NAME
    API_VTAG: VersionTag = API_VTAG

    # RUNTIME  -----------------------------------------------------------

    INVITATIONS_LOGLEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices(
                "INVITATIONS_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"
            ),
        ),
    ] = LogLevel.INFO

    INVITATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "INVITATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED",
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
        ),
    ] = False

    INVITATIONS_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices(
                "INVITATIONS_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
            ),
            description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
        ),
    ] = DEFAULT_FACTORY

    @cached_property
    def log_level(self) -> LogLevelInt:
        return cast(LogLevelInt, self.INVITATIONS_LOGLEVEL)

    @field_validator("INVITATIONS_LOGLEVEL", mode="before")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


class MinimalApplicationSettings(_BaseApplicationSettings):
    """Extends base settings with the settings needed to create invitation links

    Separated for convenience to run some commands of the CLI that
    are not related to the web server.
    """

    INVITATIONS_SWAGGER_API_DOC_ENABLED: Annotated[
        bool, Field(description="If true, it displays swagger doc at /doc")
    ] = True

    INVITATIONS_SECRET_KEY: Annotated[
        SecretStr,
        Field(
            description="Secret key to generate invitations. "
            "TIP: simcore-service-invitations generate-key",
            min_length=44,
        ),
    ]

    INVITATIONS_OSPARC_URL: Annotated[HttpUrl, Field(description="Target platform")]
    INVITATIONS_DEFAULT_PRODUCT: Annotated[
        ProductName,
        Field(
            description="Default product if not specified in the request. "
            "WARNING: this product must be defined in INVITATIONS_OSPARC_URL",
        ),
    ]


class ApplicationSettings(MinimalApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    INVITATIONS_USERNAME: Annotated[
        str,
        Field(
            description="Username for HTTP Basic Auth. Required if started as a web app.",
            min_length=3,
        ),
    ]
    INVITATIONS_PASSWORD: Annotated[
        SecretStr,
        Field(
            description="Password for HTTP Basic Auth. Required if started as a web app.",
            min_length=10,
        ),
    ]
    INVITATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True
    INVITATIONS_TRACING: Annotated[
        TracingSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="settings for opentelemetry tracing",
        ),
    ]
