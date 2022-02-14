from typing import Optional

from models_library.basic_types import BootModeEnum, BuildTargetEnum, LogLevel
from pydantic import Field
from pydantic.networks import AnyUrl
from settings_library.base import BaseCustomSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings


class PennsieveSettings(BaseCustomSettings):
    PENNSIEVE_ENABLED: bool = True

    PENNSIEVE_API_URL: AnyUrl = "https://api.pennsieve.io"
    PENNSIEVE_API_GENERAL_TIMEOUT: float = 20.0
    PENNSIEVE_HEALTCHCHECK_TIMEOUT: float = 1.0


class Settings(BaseCustomSettings, MixinLoggingSettings):
    # DOCKER
    SC_BOOT_MODE: Optional[BootModeEnum]
    SC_BOOT_TARGET: Optional[BuildTargetEnum]

    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["DATCORE-ADAPTER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )

    PENNSIEVE: PennsieveSettings = Field(auto_default_from_env=True)

    DATCORE_ADAPTER_TRACING: Optional[TracingSettings] = Field(
        auto_default_from_env=True
    )
