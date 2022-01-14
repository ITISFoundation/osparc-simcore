import logging
from typing import Optional

from pydantic import Field, validator
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import BootMode
from settings_library.utils_logging import MixinLoggingSettings


def test_mixin_logging(monkeypatch):

    monkeypatch.setenv("LOG_LEVEL", "debug")

    # -----------------------------------------------------------

    class Settings(BaseCustomSettings, MixinLoggingSettings):
        # DOCKER
        SC_BOOT_MODE: Optional[BootMode]

        # LOGGING
        LOG_LEVEL: str = Field(
            "WARNING",
            env=[
                "APPNAME_LOG_LEVEL",
                "LOG_LEVEL",
            ],
        )

        APPNAME_DEBUG: bool = Field(False, description="Starts app in debug mode")

        @validator("LOG_LEVEL")
        @classmethod
        def _v(cls, value) -> str:
            return cls.validate_log_level(value)

    # -----------------------------------------------------------

    settings = Settings()

    # test validator
    assert settings.LOG_LEVEL == "DEBUG"

    assert (
        settings.json()
        == '{"SC_BOOT_MODE": null, "LOG_LEVEL": "DEBUG", "APPNAME_DEBUG": false}'
    )

    # test cached-property
    assert settings.log_level == logging.DEBUG
    # log_level is cached-property (notice that is lower-case!), and gets added after first use
    assert (
        settings.json()
        == '{"SC_BOOT_MODE": null, "LOG_LEVEL": "DEBUG", "APPNAME_DEBUG": false, "log_level": 10}'
    )
