from functools import cached_property

from models_library.products import ProductName
from pydantic import Field, HttpUrl, PositiveInt, SecretStr, validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import BuildTargetEnum, LogLevel, VersionTag
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME


class _BaseApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    """Base settings of any osparc service's app"""

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

    INVITATIONS_LOGLEVEL: LogLevel = Field(
        default=LogLevel.INFO, env=["INVITATIONS_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )
    INVITATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "INVITATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    INVITATIONS_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        env=["INVITATIONS_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"],
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )

    @cached_property
    def LOG_LEVEL(self):
        return self.INVITATIONS_LOGLEVEL

    @validator("INVITATIONS_LOGLEVEL", pre=True)
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


class MinimalApplicationSettings(_BaseApplicationSettings):
    """Extends base settings with the settings needed to create invitation links

    Separated for convenience to run some commands of the CLI that
    are not related to the web server.
    """

    INVITATIONS_SWAGGER_API_DOC_ENABLED: bool = Field(
        default=True, description="If true, it displays swagger doc at /doc"
    )

    INVITATIONS_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to generate invitations. "
        "TIP: simcore-service-invitations generate-key",
        min_length=44,
    )

    INVITATIONS_OSPARC_URL: HttpUrl = Field(..., description="Target platform")
    INVITATIONS_DEFAULT_PRODUCT: ProductName = Field(
        ...,
        description="Default product if not specified in the request. "
        "WARNING: this product must be defined in INVITATIONS_OSPARC_URL",
    )


class ApplicationSettings(MinimalApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    INVITATIONS_USERNAME: str = Field(
        ...,
        description="Username for HTTP Basic Auth. Required if started as a web app.",
        min_length=3,
    )
    INVITATIONS_PASSWORD: SecretStr = Field(
        ...,
        description="Password for HTTP Basic Auth. Required if started as a web app.",
        min_length=10,
    )
    INVITATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True
    INVITATIONS_TRACING: TracingSettings | None = Field(
        auto_default_from_env=True, description="settings for opentelemetry tracing"
    )
