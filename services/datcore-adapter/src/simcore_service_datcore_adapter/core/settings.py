from functools import cached_property
from typing import Optional, cast

from models_library.basic_types import BootModeEnum, LogLevel
from pydantic import Field, parse_obj_as, validator
from pydantic.networks import AnyUrl
from settings_library.base import BaseCustomSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings


class PennsieveSettings(BaseCustomSettings):
    PENNSIEVE_ENABLED: bool = True

    PENNSIEVE_API_URL: AnyUrl = parse_obj_as(AnyUrl, "https://api.pennsieve.io")
    PENNSIEVE_API_GENERAL_TIMEOUT: float = 20.0
    PENNSIEVE_HEALTCHCHECK_TIMEOUT: float = 1.0


class Settings(BaseCustomSettings, MixinLoggingSettings):
    # DOCKER
    SC_BOOT_MODE: Optional[BootModeEnum]

    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=[
            "DATCORE_ADAPTER_LOGLEVEL",
            "DATCORE_ADAPTER_LOG_LEVEL",
            "LOG_LEVEL",
            "LOGLEVEL",
        ],
    )

    PENNSIEVE: PennsieveSettings = Field(auto_default_from_env=True)

    DATCORE_ADAPTER_TRACING: Optional[TracingSettings] = Field(
        auto_default_from_env=True
    )

    @cached_property
    def debug(self) -> bool:
        """If True, debug tracebacks should be returned on errors."""
        return self.SC_BOOT_MODE in [
            BootModeEnum.DEBUG,
            BootModeEnum.DEVELOPMENT,
            BootModeEnum.LOCAL,
        ]

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        return cast(str, cls.validate_log_level(value))
