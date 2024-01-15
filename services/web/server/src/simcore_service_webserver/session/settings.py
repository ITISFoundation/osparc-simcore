from typing import Final

from aiohttp import web
from pydantic import PositiveInt
from pydantic.class_validators import validator
from pydantic.fields import Field
from pydantic.types import SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.utils_session import MixinSessionSettings

from .._constants import APP_SETTINGS_KEY

_MINUTE: Final[int] = 60  # secs
_HOUR: Final[int] = 60 * _MINUTE
_DAY: Final[int] = 24 * _HOUR


class SessionSettings(BaseCustomSettings, MixinSessionSettings):

    SESSION_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to encrypt cookies. "
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
        env=["SESSION_SECRET_KEY", "WEBSERVER_SESSION_SECRET_KEY"],
    )

    SESSION_ACCESS_TOKENS_EXPIRATION_INTERVAL_SECS: int = Field(
        30 * _MINUTE,
        description="Time interval for session access tokens to expire since creation",
    )

    # Cookies attributes
    # - https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies
    # - Defaults taken from https://github.com/aio-libs/aiohttp-session/blob/master/aiohttp_session/cookie_storage.py#L20-L26
    #

    SESSION_COOKIE_NAME: str = Field(
        default="osparc.WEBAPI_SESSION",
        min_length=4,
        description="Name of the session's cookie",
    )

    SESSION_COOKIE_MAX_AGE: PositiveInt | None = Field(
        default=None,
        description="Max-Age attribute. Maximum age for session data, int seconds or None for “session cookie” which last until you close your browser.",
    )
    SESSION_COOKIE_SAMESITE: str | None = Field(
        default=None,
        description="SameSite attribute lets servers specify whether/when cookies are sent with cross-site requests",
    )
    SESSION_COOKIE_SECURE: bool = Field(
        default=True,
        description="Ensures the cookie is only sent over secure HTTPS connections",
    )
    SESSION_COOKIE_HTTPONLY: bool = Field(
        default=True,
        description="This prevents JavaScript from accessing the session cookie",
    )

    @validator("SESSION_SECRET_KEY")
    @classmethod
    def check_valid_fernet_key(cls, v):
        return cls.do_check_valid_fernet_key(v)

    @validator("SESSION_COOKIE_SAMESITE")
    @classmethod
    def check_valid_samesite_attribute(cls, v):
        # NOTE: Replacement to `Literal["Strict", "Lax"] | None` due to bug in settings_library/base.py:93: in prepare_field
        if v is not None and v not in ("Strict", "Lax"):
            msg = "Invalid {v}. Expected Strict, Lax or None"
            raise ValueError(msg)


def get_plugin_settings(app: web.Application) -> SessionSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_SESSION
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, SessionSettings)  # nosec
    return settings
