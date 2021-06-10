import logging
from typing import Optional

from models_library.basic_types import BootModeEnum
from models_library.settings.base import BaseCustomSettings
from pydantic import Field, validator


class MixinLoggingSettings:

    # TODO: test upon construction that LOG_LEVEL exists in subclass!

    @validator("LOG_LEVEL")
    @classmethod
    def match_logging_level(cls, value) -> str:
        try:
            getattr(logging, value.upper())
        except AttributeError as err:
            raise ValueError(f"{value.upper()} is not a valid level") from err
        return value.upper()

    @property
    def log_level(self) -> int:
        """ Can be used in logging.setLogLevel() """
        assert issubclass(self.__class__, MixinLoggingSettings)  # nosec
        return getattr(logging, getattr(self, "LOG_LEVEL"))  # pylint: disable=no-member


class Settings(BaseCustomSettings, MixinLoggingSettings):
    # TODO: common settings of all apps

    # DOCKER
    SC_BOOT_MODE: Optional[BootModeEnum]

    # LOGGING
    LOG_LEVEL: str = Field(
        "DEBUG",
        env=[
            "WORKFLOW_LOG_LEVEL",
            "LOG_LEVEL",
        ],
    )

    WORKFLOW_DEBUG: bool = Field(False, description="Starts app in debug mode")
