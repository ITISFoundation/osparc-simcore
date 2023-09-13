from functools import cached_property
from typing import cast

from pydantic import (
    Field,
    HttpUrl,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    parse_obj_as,
    validator,
)
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import BuildTargetEnum, LogLevel, VersionTag
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

    PAYMENTS_LOGLEVEL: LogLevel = Field(
        default=LogLevel.INFO, env=["PAYMENTS_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )
    PAYMENTS_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "PAYMENTS_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )

    @cached_property
    def LOG_LEVEL(self):  # noqa: N802
        return self.PAYMENTS_LOGLEVEL

    @validator("PAYMENTS_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))


class ApplicationSettings(_BaseApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    PAYMENTS_GATEWAY_URL: HttpUrl = Field(
        ..., description="Base url to the payment gateway"
    )

    PAYMENTS_GATEWAY_API_KEY: SecretStr
    PAYMENTS_GATEWAY_API_SECRET: SecretStr

    PAYMENTS_USERNAME: str = Field(
        ...,
        description="Username for HTTP Basic Auth. Required if started as a web app.",
        min_length=3,
    )
    PAYMENTS_PASSWORD: SecretStr = Field(
        ...,
        description="Password for HTTP Basic Auth. Required if started as a web app.",
        min_length=10,
    )

    PAYMENTS_ACCESS_TOKEN_SECRET_KEY: SecretStr = Field(
        ...,
        description="To generate a random password with openssl in hex format with 32 bytes, run `openssl rand -hex 32`",
        min_length=30,
    )
    PAYMENTS_ACCESS_TOKEN_EXPIRE_MINUTES: PositiveFloat = Field(default=30)

    PAYMENTS_RABBITMQ: RabbitSettings = Field(
        auto_default_from_env=True, description="settings for service/rabbitmq"
    )
