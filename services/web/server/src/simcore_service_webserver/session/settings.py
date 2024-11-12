from typing import Annotated, Final

from aiohttp import web
from pydantic import AliasChoices, PositiveInt, field_validator
from pydantic.fields import Field
from pydantic.types import SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.utils_session import MixinSessionSettings

from .._constants import APP_SETTINGS_KEY

_MINUTE: Final[int] = 60  # secs


class SessionSettings(BaseCustomSettings, MixinSessionSettings):

    SESSION_SECRET_KEY: Annotated[
        SecretStr,
        Field(
            ...,
            description="Secret key to encrypt cookies. "
            'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
            min_length=44,
            validation_alias=AliasChoices(
                "SESSION_SECRET_KEY", "WEBSERVER_SESSION_SECRET_KEY"
            ),
        ),
    ]

    SESSION_ACCESS_TOKENS_EXPIRATION_INTERVAL_SECS: int = Field(
        30 * _MINUTE,
        description="Time interval for session access tokens to expire since creation",
    )

    # Cookies attributes
    # - https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies
    # - Defaults taken from https://github.com/aio-libs/aiohttp-session/blob/master/aiohttp_session/cookie_storage.py#L20-L26
    #

    SESSION_COOKIE_MAX_AGE: Annotated[
        PositiveInt | None,
        Field(
            default=None,
            description="Max-Age attribute. Maximum age for session data, int seconds or None for “session cookie” which last until you close your browser.",
        ),
    ]
    SESSION_COOKIE_SAMESITE: str | None = Field(
        default=None,
        description="SameSite attribute lets servers specify whether/when cookies are sent with cross-site requests",
    )
    SESSION_COOKIE_SECURE: bool = Field(
        default=False,
        description="Ensures the cookie is only sent over secure HTTPS connections",
        # NOTE: careful in tests keep it False!
    )
    SESSION_COOKIE_HTTPONLY: bool = Field(
        default=True,
        description="This prevents JavaScript from accessing the session cookie",
    )

    @field_validator("SESSION_SECRET_KEY")
    @classmethod
    def check_valid_fernet_key(cls, v):
        return cls.do_check_valid_fernet_key(v)

    @field_validator("SESSION_COOKIE_SAMESITE")
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
