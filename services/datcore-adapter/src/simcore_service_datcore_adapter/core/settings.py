from typing import Optional

from models_library.basic_types import BootModeEnum, BuildTargetEnum, LogLevel
from pydantic import Field
from pydantic.networks import AnyUrl
from settings_library.base import BaseCustomSettings
from settings_library.logging_utils import MixinLoggingSettings


class PennsieveSettings(BaseCustomSettings):
    ENABLED: bool = True

    URL: AnyUrl = "https://api.pennsieve.io"


class Settings(BaseCustomSettings, MixinLoggingSettings):
    # DOCKER
    SC_BOOT_MODE: Optional[BootModeEnum]
    SC_BOOT_TARGET: Optional[BuildTargetEnum]

    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["DATCORE-ADAPTER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )

    PENNSIEVE: PennsieveSettings
