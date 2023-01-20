from typing import Final

from aiohttp import web
from pydantic.class_validators import validator
from pydantic.fields import Field
from pydantic.types import SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.utils_session import MixinSessionSettings

from ._constants import APP_SETTINGS_KEY

_MINUTES: Final[int] = 60  # secs


class SessionSettings(BaseCustomSettings, MixinSessionSettings):

    SESSION_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to encrypt cookies. "
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
        env=["SESSION_SECRET_KEY", "WEBSERVER_SESSION_SECRET_KEY"],
    )

    SESSION_ACCESS_TOKENS_EXPIRATION_INTERVAL_SECS: int = Field(
        30 * _MINUTES,
        description="Time interval for session access tokens to expire since creation",
    )

    @validator("SESSION_SECRET_KEY")
    @classmethod
    def check_valid_fernet_key(cls, v):
        return cls.do_check_valid_fernet_key(v)


def get_plugin_settings(app: web.Application) -> SessionSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_SESSION
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, SessionSettings)  # nosec
    return settings
