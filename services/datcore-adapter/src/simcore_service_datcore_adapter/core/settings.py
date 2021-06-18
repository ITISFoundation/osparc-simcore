from typing import Optional

from models_library.basic_types import BootModeEnum, BuildTargetEnum, LogLevel
from models_library.settings.base import BaseCustomSettings
from models_library.settings.postgres import PostgresSettings
from pydantic import Field


class Settings(BaseCustomSettings):
    # DOCKER
    SC_BOOT_MODE: Optional[BootModeEnum]
    SC_BOOT_TARGET: Optional[BuildTargetEnum]


    DATCORE-ADAPTER_LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO, env=["DATCORE-ADAPTER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )

    DATCORE-ADAPTER_POSTGRES: PostgresSettings

    @classmethod
    def create_from_envs(cls) -> "Settings":
        cls.set_defaults_with_default_constructors(
            [
                ("DATCORE-ADAPTER_POSTGRES", PostgresSettings),
            ]
        )
        return cls()
