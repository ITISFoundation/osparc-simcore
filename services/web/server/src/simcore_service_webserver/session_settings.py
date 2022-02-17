from aiohttp import web
from pydantic.class_validators import validator
from pydantic.fields import Field
from pydantic.types import SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.utils_session import MixinSessionSettings

from ._constants import APP_SETTINGS_KEY


class SessionSettings(BaseCustomSettings, MixinSessionSettings):

    SESSION_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to encrypt cookies. "
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
        env=["SESSION_SECRET_KEY", "WEBSERVER_SESSION_SECRET_KEY"],
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


def assert_valid_config(secret_key: str):

    WEBSERVER_SESSION = SessionSettings()
    assert (  # nosec
        WEBSERVER_SESSION.SESSION_SECRET_KEY.get_secret_value() == secret_key
    )  # nosec
