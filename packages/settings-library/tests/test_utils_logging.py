import logging
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import BootModeEnum
from settings_library.utils_logging import MixinLoggingSettings


def test_mixin_logging(monkeypatch):

    monkeypatch.setenv("LOG_LEVEL", "debug")

    # -----------------------------------------------------------

    class Settings(BaseCustomSettings, MixinLoggingSettings):
        # DOCKER
        SC_BOOT_MODE: BootModeEnum | None = None

        # LOGGING
        LOG_LEVEL: Annotated[
            str,
            Field(
                validation_alias=AliasChoices(
                    "APPNAME_LOG_LEVEL",
                    "LOG_LEVEL",
                ),
            ),
        ] = "WARNING"

        APPNAME_DEBUG: Annotated[
            bool, Field(description="Starts app in debug mode")
        ] = False

        @field_validator("LOG_LEVEL", mode="before")
        @classmethod
        def _v(cls, value: str) -> str:
            return cls.validate_log_level(value)

    # -----------------------------------------------------------

    settings = Settings()

    # test validator
    assert settings.LOG_LEVEL == "DEBUG"

    assert (
        settings.model_dump_json()
        == '{"SC_BOOT_MODE":null,"LOG_LEVEL":"DEBUG","APPNAME_DEBUG":false}'
    )

    # test cached-property
    assert settings.log_level == logging.DEBUG
