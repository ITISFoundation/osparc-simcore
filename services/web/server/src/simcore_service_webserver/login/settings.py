from datetime import timedelta
from typing import Annotated, Final, Literal

from aiohttp import web
from pydantic import BaseModel, ValidationInfo, field_validator
from pydantic.fields import Field
from pydantic.types import PositiveFloat, PositiveInt, SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.email import EmailProtocol
from settings_library.twilio import TwilioSettings
from simcore_postgres_database.models.products import ProductLoginSettingsDict

from ._constants import APP_LOGIN_SETTINGS_PER_PRODUCT_KEY

_DAYS: Final[float] = 1.0  # in days
_MINUTES: Final[float] = 1.0 / 24.0 / 60.0  # in days
_YEARS: Final[float] = 365 * _DAYS
_UNLIMITED: Final[float] = 99 * _YEARS

APP_LOGIN_OPTIONS_KEY = f"{__name__}.APP_LOGIN_OPTIONS_KEY"


class LoginSettings(BaseCustomSettings):
    LOGIN_ACCOUNT_DELETION_RETENTION_DAYS: Annotated[
        PositiveInt,
        Field(
            default=30,
            description="Retention time (in days) of all the data after a user has requested the deletion of their account"
            "NOTE: exposed to the front-end as `to_client_statics`",
        ),
    ]

    LOGIN_REGISTRATION_CONFIRMATION_REQUIRED: bool = Field(
        default=True,
    )

    LOGIN_REGISTRATION_INVITATION_REQUIRED: bool = Field(
        ...,
    )

    LOGIN_TWILIO: TwilioSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True},
        description="Twilio service settings. Used to send SMS for 2FA",
    )

    LOGIN_2FA_CODE_EXPIRATION_SEC: PositiveInt = Field(
        default=120, description="Expiration time for code [sec]"
    )

    LOGIN_2FA_REQUIRED: Annotated[
        bool,
        Field(
            default=False,
            description="If true, it enables two-factor authentication (2FA)",
        ),
    ]

    LOGIN_PASSWORD_MIN_LENGTH: PositiveInt = Field(
        default=12,
        description="Minimum length of password",
    )

    @field_validator("LOGIN_2FA_REQUIRED")
    @classmethod
    def _login_2fa_needs_email_registration(cls, v, info: ValidationInfo):
        # NOTE: this constraint ensures that a phone is registered in current workflow
        if v and not info.data.get("LOGIN_REGISTRATION_CONFIRMATION_REQUIRED", False):
            msg = "Cannot enable 2FA w/o email confirmation"
            raise ValueError(msg)
        return v

    @field_validator("LOGIN_2FA_REQUIRED")
    @classmethod
    def _login_2fa_needs_sms_service(cls, v, info: ValidationInfo):
        if v and info.data.get("LOGIN_TWILIO") is None:
            msg = "Cannot enable 2FA w/o twilio settings which is used to send SMS"
            raise ValueError(msg)
        return v


class LoginSettingsForProduct(LoginSettings):
    """
    Customization of these plugin settings for a product

    LoginSettings are created (and frozen) upon creation of the app and available
    to the plugin for setup_login.

    LoginSettingsForProduct is obtained composing those with the overrides defined for each
    product in the  database.

    This is initialized for each product during on_startup events at the setup_login
    """

    @classmethod
    def create_from_composition(
        cls,
        app_login_settings: LoginSettings,
        product_login_settings: ProductLoginSettingsDict,
    ) -> "LoginSettingsForProduct":
        """
        For the LoginSettings, product-specific settings override app-specifics settings
        """
        composed_settings = {
            **app_login_settings.model_dump(),
            **product_login_settings,
        }

        if "two_factor_enabled" in composed_settings:
            # legacy safe
            composed_settings["LOGIN_2FA_REQUIRED"] = composed_settings.pop(
                "two_factor_enabled"
            )
        return cls(**composed_settings)


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
    SMTP_USERNAME: str | None = Field(...)
    SMTP_PASSWORD: SecretStr | None = Field(...)

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


def get_plugin_settings(
    app: web.Application, product_name: str
) -> LoginSettingsForProduct:
    """login plugin's settings are customized per product"""
    settings = app[APP_LOGIN_SETTINGS_PER_PRODUCT_KEY][product_name]
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, LoginSettingsForProduct)  # nosec
    return settings


def get_plugin_options(app: web.Application) -> LoginOptions:
    options = app.get(APP_LOGIN_OPTIONS_KEY)
    assert options, "login plugin was not initialized"  # nosec
    assert isinstance(options, LoginOptions)  # nosec
    return options
