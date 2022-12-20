from datetime import timedelta
from typing import Final, Literal, Optional

from aiohttp import web
from pydantic import BaseModel, validator
from pydantic.fields import Field
from pydantic.types import PositiveFloat, PositiveInt, SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.email import EmailProtocol
from settings_library.twilio import TwilioSettings

from .._constants import APP_SETTINGS_KEY

_DAYS: Final[float] = 1.0  # in days
_MINUTES: Final[float] = 1.0 / 24.0 / 60.0  # in days
_YEARS: Final[float] = 365 * _DAYS
_UNLIMITED: Final[float] = 99 * _YEARS

APP_LOGIN_OPTIONS_KEY = f"{__name__}.APP_LOGIN_OPTIONS_KEY"


class LoginSettings(BaseCustomSettings):
    LOGIN_REGISTRATION_CONFIRMATION_REQUIRED: bool = Field(
        True,
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

    LOGIN_TWILIO: Optional[TwilioSettings] = Field(
        auto_default_from_env=True,
        description="Twilio service settings. Used to send SMS for 2FA",
    )

    LOGIN_2FA_REQUIRED: bool = Field(
        default=False,
        description="Use products.login.two_factor_enabled instead",
        deprecated=True,
    )

    LOGIN_2FA_CODE_EXPIRATION_SEC: PositiveInt = Field(
        default=60.0, description="Expiration time for code [sec]"
    )

    @validator("LOGIN_2FA_REQUIRED")
    @classmethod
    def login_2fa_needs_email_registration(cls, v, values):
        # NOTE: this constraint ensures that a phone is registered in current workflow
        if v and not values.get("LOGIN_REGISTRATION_CONFIRMATION_REQUIRED", False):
            raise ValueError("Cannot enable 2FA w/o email confirmation")
        return v

    @validator("LOGIN_2FA_REQUIRED")
    @classmethod
    def login_2fa_needs_sms_service(cls, v, values):
        if v and values.get("LOGIN_TWILIO") is None:
            raise ValueError(
                "Cannot enable 2FA w/o twilio settings which is used to send SMS"
            )
        return v


class LoginOptions(BaseModel):
    """These options are NOT directly exposed to the env vars due to security reasons.

    NOTE: This is legacy from first version and should not be extended anymore
    """

    PASSWORD_LEN: tuple[PositiveInt, PositiveInt] = (6, 30)
    LOGIN_REDIRECT: str = "/"
    LOGOUT_REDIRECT: str = "/"

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_PROTOCOL: EmailProtocol
    SMTP_USERNAME: Optional[str] = Field(...)
    SMTP_PASSWORD: Optional[SecretStr] = Field(...)

    # NOTE: lifetime limits are expressed in days (use constants above)
    REGISTRATION_CONFIRMATION_LIFETIME: PositiveFloat = 5 * _DAYS
    INVITATION_CONFIRMATION_LIFETIME: PositiveFloat = _UNLIMITED
    RESET_PASSWORD_CONFIRMATION_LIFETIME: PositiveFloat = 20 * _MINUTES
    CHANGE_EMAIL_CONFIRMATION_LIFETIME: PositiveFloat = 5 * _DAYS

    def get_confirmation_lifetime(
        self,
        action: Literal["REGISTRATION", "INVITATION", "RESET_PASSWORD", "CHANGE_EMAIL"],
    ) -> timedelta:
        value = getattr(self, f"{action.upper()}_CONFIRMATION_LIFETIME")
        return timedelta(days=value)


def get_plugin_settings(app: web.Application) -> LoginSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_LOGIN
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, LoginSettings)  # nosec
    return settings


def get_plugin_options(app: web.Application) -> LoginOptions:
    options = app.get(APP_LOGIN_OPTIONS_KEY)
    assert options, "login plugin was not initialized"  # nosec
    assert isinstance(options, LoginOptions)  # nosec
    return options
