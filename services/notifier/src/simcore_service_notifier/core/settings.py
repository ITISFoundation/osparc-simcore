from functools import cached_property
from typing import cast

from pydantic import Field, parse_obj_as, validator
from settings_library.application import BaseApplicationSettings
from settings_library.basic_types import LogLevel, VersionTag
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME


class _BaseApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    """Base settings of any osparc service's app"""

    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = PROJECT_NAME
    API_VTAG: VersionTag = parse_obj_as(VersionTag, API_VTAG)

    # RUNTIME  -----------------------------------------------------------

    NOTIFIER_LOGLEVEL: LogLevel = Field(
        default=LogLevel.INFO, env=["NOTIFIER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )
    NOTIFIER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "NOTIFIER_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )

    @cached_property
    def LOG_LEVEL(self):  # noqa: N802
        return self.NOTIFIER_LOGLEVEL

    @validator("NOTIFIER_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))


class ApplicationSettings(_BaseApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    NOTIFIER_RABBITMQ: RabbitSettings = Field(
        auto_default_from_env=True, description="settings for service/rabbitmq"
    )

    NOTIFIER_POSTGRES: PostgresSettings = Field(
        auto_default_from_env=True, description="settings for postgres service"
    )
