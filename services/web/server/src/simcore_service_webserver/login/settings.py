from datetime import timedelta
from typing import Literal, Optional, Tuple

from aiohttp import web
from pydantic import BaseModel
from pydantic.fields import Field
from pydantic.types import PositiveFloat, PositiveInt, SecretStr
from settings_library.base import BaseCustomSettings

from .._constants import APP_SETTINGS_KEY
from .storage import AsyncpgStorage

_DAYS = 1.0
_MINUTES = 1.0 / 24.0 / 60.0


APP_LOGIN_STORAGE_KEY = f"{__name__}.APP_LOGIN_STORAGE_KEY"
APP_LOGIN_OPTIONS_KEY = f"{__name__}.APP_LOGIN_OPTIONS_KEY"


class LoginSettings(BaseCustomSettings):
    LOGIN_REGISTRATION_CONFIRMATION_REQUIRED: bool = Field(
        ...,
        env=[
            "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED",
            "WEBSERVER_LOGIN_REGISTRATION_CONFIRMATION_REQUIRED",
        ],
    )
    LOGIN_REGISTRATION_INVITATION_REQUIRED: bool = Field(
        ...,
        env=[
            "LOGIN_REGISTRATION_INVITATION_REQUIRED",
            "WEBSERVER_LOGIN_REGISTRATION_INVITATION_REQUIRED",
        ],
    )


class LoginOptions(BaseModel):
    """These options are NOT directly exposed to the env vars due to security reasons."""

    THEME: str = "templates/osparc.io"
    COMMON_THEME: str = "templates/common"
    PASSWORD_LEN: Tuple[PositiveInt, PositiveInt] = (6, 30)
    LOGIN_REDIRECT: str = "/"
    LOGOUT_REDIRECT: str = "/"

    SMTP_SENDER: Optional[str] = None
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_TLS_ENABLED: bool = False
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[SecretStr] = None

    # lifetime limits are in days
    REGISTRATION_CONFIRMATION_LIFETIME: PositiveFloat = 5 * _DAYS
    INVITATION_CONFIRMATION_LIFETIME: PositiveFloat = 15 * _DAYS
    RESET_PASSWORD_CONFIRMATION_LIFETIME: PositiveFloat = 20 * _MINUTES
    CHANGE_EMAIL_CONFIRMATION_LIFETIME: PositiveFloat = 5 * _DAYS

    def get_confirmation_lifetime(
        self,
        action: Literal["REGISTRATION", "INVITATION", "RESET_PASSWORD", "CHANGE_EMAIL"],
    ) -> timedelta:
        value = getattr(self, f"{action.upper()}_CONFIRMATION_LIFETIME")
        return timedelta(days=value)

    # TODO: translation?
    MSG_LOGGED_IN: str = "You are logged in"
    MSG_LOGGED_OUT: str = "You are logged out"
    MSG_ACTIVATED: str = "Your account is activated"
    MSG_UNKNOWN_EMAIL: str = "This email is not registered"
    MSG_WRONG_PASSWORD: str = "Wrong password"
    MSG_PASSWORD_MISMATCH: str = "Password and confirmation do not match"
    MSG_USER_BANNED: str = "This user is banned"
    MSG_ACTIVATION_REQUIRED: str = (
        "You have to activate your account via email, before you can login",
    )
    MSG_EMAIL_EXISTS: str = "This email is already registered"
    MSG_OFTEN_RESET_PASSWORD: str = (
        (
            "You can not request of restoring your password so often. Please, use"
            " the link we sent you recently"
        ),
    )
    MSG_CANT_SEND_MAIL: str = "Can't send email, try a little later"
    MSG_PASSWORDS_NOT_MATCH: str = "Passwords must match"
    MSG_PASSWORD_CHANGED: str = "Your password is changed"
    MSG_CHANGE_EMAIL_REQUESTED: str = (
        "Please, click on the verification link" " we sent to your new email address"
    )
    MSG_EMAIL_CHANGED: str = "Your email is changed"
    MSG_AUTH_FAILED: str = "Authorization failed"
    MSG_EMAIL_SENT: str = (
        "An email has been sent to {email} with further instructions",
    )


def get_plugin_settings(app: web.Application) -> LoginSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_LOGIN
    assert settings, "login plugin was not initialized"  # nosec
    return settings


def get_plugin_options(app: web.Application) -> LoginOptions:
    options = app.get(APP_LOGIN_OPTIONS_KEY)
    assert options, "login plugin was not initialized"  # nosec
    return options


def get_plugin_storage(app: web.Application) -> AsyncpgStorage:
    storage = app.get(APP_LOGIN_STORAGE_KEY)
    assert storage, "login plugin was not initialized"  # nosec
    return storage
