from typing import Optional

from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    VersionTag,
)
from pydantic import Field, HttpUrl, PositiveInt, SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, APP_NAME


class BaseApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: Optional[str] = None
    SC_BUILD_TARGET: Optional[BuildTargetEnum] = None
    SC_VCS_REF: Optional[str] = None
    SC_VCS_URL: Optional[str] = None

    # @Dockerfile
    SC_BOOT_MODE: Optional[BootModeEnum] = None
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


class DesktopApplicationSettings(BaseApplicationSettings):
    """Desktop app's environs"""

    INVITATIONS_MAKER_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to generate invitations"
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
    )

    INVITATIONS_MAKER_OSPARC_URL: HttpUrl = Field(..., description="Target platform")


class WebApplicationSettings(DesktopApplicationSettings):
    """Web app's environs"""

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
