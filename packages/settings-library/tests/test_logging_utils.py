import logging
from typing import Optional

from pydantic import Field
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import BootModeEnum
from settings_library.logging_utils import MixinLoggingSettings


def test_mixin_logging(monkeypatch):

    monkeypatch.setenv("LOG_LEVEL", "debug")

    class _Settings(BaseCustomSettings, MixinLoggingSettings):
        # TODO: common settings of all apps

        # DOCKER
        SC_BOOT_MODE: Optional[BootModeEnum]

        # LOGGING
        LOG_LEVEL: str = Field(
            "DEBUG",
            env=[
                "APPNAME_LOG_LEVEL",
                "LOG_LEVEL",
            ],
        )

        APPNAME_DEBUG: bool = Field(False, description="Starts app in debug mode")

    settings = _Settings()
    assert settings.log_level == logging.DEBUG
