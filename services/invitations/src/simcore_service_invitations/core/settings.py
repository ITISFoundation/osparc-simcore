from functools import cached_property
from typing import Optional, cast

from pydantic import Field, HttpUrl, PositiveInt, SecretStr, root_validator, validator
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import BuildTargetEnum, LogLevel, VersionTag
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
    SC_BUILD_DATE: Optional[str] = None
    SC_BUILD_TARGET: Optional[BuildTargetEnum] = None
    SC_VCS_REF: Optional[str] = None
    SC_VCS_URL: Optional[str] = None

    # @Dockerfile
    SC_BOOT_TARGET: Optional[BuildTargetEnum] = None
    SC_HEALTHCHECK_TIMEOUT: Optional[PositiveInt] = Field(
        None,
        description="If a single run of the check takes longer than timeout seconds "
        "then the check is considered to have failed."
        "It takes retries consecutive failures of the health check for the container to be considered unhealthy.",
    )
    SC_USER_ID: Optional[int] = None
    SC_USER_NAME: Optional[str] = None

    # RUNTIME  -----------------------------------------------------------

    INVITATIONS_LOGLEVEL: LogLevel = Field(
        LogLevel.INFO, env=["INVITATIONS_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )

    @cached_property
    def LOG_LEVEL(self):
        return self.INVITATIONS_LOGLEVEL

    @validator("INVITATIONS_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))


class MinimalApplicationSettings(_BaseApplicationSettings):
    """Extends base settings with the settings needed to create invitation links

    Separated for convenience to run some commands of the CLI that
    are not related to the web server.
    """

    INVITATIONS_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to generate invitations"
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
    )

    INVITATIONS_OSPARC_URL: HttpUrl = Field(..., description="Target platform")


class ApplicationSettings(MinimalApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API

    Set both INVITATIONS_USERNAME and INVITATIONS_PASSWORD to None to disable authentication
    """

    INVITATIONS_USERNAME: Optional[str] = Field(
        ...,
        description="Username for HTTP Basic Auth",
        min_length=3,
    )
    INVITATIONS_PASSWORD: Optional[SecretStr] = Field(
        ...,
        description="Password for HTTP Basic Auth",
        min_length=10,
    )

    @cached_property
    def is_auth_enabled(self) -> bool:
        return (
            self.INVITATIONS_USERNAME is not None
            and self.INVITATIONS_PASSWORD is not None
        )

    @root_validator
    @classmethod
    def check_complete_auth_state(cls, values):
        # either both None or none of them is None
        username = values.get("INVITATIONS_USERNAME")
        password = values.get("INVITATIONS_PASSWORD")

        if (username is None and password is not None) or (
            username is not None and password is None
        ):
            raise ValueError(
                f"To disable auth, set username==password==None. Partial None is not allowed, got {username=}, {password=}"
            )

        return values
