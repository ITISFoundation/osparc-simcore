from typing import Optional

from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    VersionTag,
)
from models_library.settings.base import BaseCustomSettings
from pydantic import Field, PositiveInt
from settings_library.utils_logging import MixinLoggingSettings


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
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
