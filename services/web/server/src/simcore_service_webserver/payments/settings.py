import os
from functools import cached_property

from aiohttp import web
from models_library.basic_types import NonNegativeDecimal
from pydantic import (
    Field,
    HttpUrl,
    PositiveInt,
    SecretStr,
    TypeAdapter,
    ValidationInfo,
    field_validator,
)
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.utils_service import (
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)

from .._constants import APP_SETTINGS_KEY


class PaymentsSettings(BaseCustomSettings, MixinServiceSettings):
    PAYMENTS_HOST: str = "payments"
    PAYMENTS_PORT: PortInt = DEFAULT_FASTAPI_PORT
    PAYMENTS_VTAG: VersionTag = TypeAdapter(VersionTag).validate_python("v1")

    PAYMENTS_USERNAME: str = Field(
        ...,
        description="Username for HTTP Basic Auth. Required if started as a web app.",
        min_length=3,
    )
    PAYMENTS_PASSWORD: SecretStr = Field(
        ...,
        description="Password for HTTP Basic Auth. Required if started as a web app.",
        min_length=10,
    )

    # NOTE: PAYMENTS_FAKE_* settings are temporary until some features are moved to the payments service
    PAYMENTS_FAKE_COMPLETION: bool = Field(
        default=False, description="Enables fake completion. ONLY for testing purposes"
    )

    PAYMENTS_FAKE_COMPLETION_DELAY_SEC: PositiveInt = Field(
        default=10,
        description="Delay in seconds sbefore completion. ONLY for testing purposes",
    )

    PAYMENTS_FAKE_GATEWAY_URL: HttpUrl = Field(
        default=TypeAdapter(HttpUrl).validate_python(
            "https://fake-payment-gateway.com"
        ),
        description="FAKE Base url to the payment gateway",
    )

    PAYMENTS_AUTORECHARGE_MIN_BALANCE_IN_CREDITS: NonNegativeDecimal = Field(
        default=100,
        description="Minimum balance in credits to top-up for auto-recharge",
        # NOTE: Using credits (instead of USD) simplify RUT monitoring which is reponsible to trigger auto-recharge
    )

    PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT: NonNegativeDecimal = Field(
        default=100,
        description="Default value in USD on the amount to top-up for auto-recharge (`top_up_amount_in_usd`)",
    )

    PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT: NonNegativeDecimal | None = Field(
        default=10000,
        description="Default value in USD for the montly limit for auto-recharge (`monthly_limit_in_usd`)",
    )

    @cached_property
    def api_base_url(self) -> str:
        # http://payments:8000/v1
        base_url_with_vtag: str = self._compose_url(
            prefix="PAYMENTS",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )
        return base_url_with_vtag

    @cached_property
    def base_url(self) -> str:
        # http://payments:8000
        base_url_without_vtag: str = self._compose_url(
            prefix="PAYMENTS",
            port=URLPart.REQUIRED,
            vtag=URLPart.EXCLUDE,
        )
        return base_url_without_vtag

    @field_validator("PAYMENTS_FAKE_COMPLETION")
    @classmethod
    def _payments_cannot_be_faken_in_production(cls, v):
        if v is True and "production" in os.environ.get("SWARM_STACK_NAME", ""):
            msg = "PAYMENTS_FAKE_COMPLETION only allowed FOR TESTING PURPOSES and cannot be released to production"
            raise ValueError(msg)
        return v

    @field_validator("PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT")
    @classmethod
    def _monthly_limit_greater_than_top_up(cls, v, info: ValidationInfo):
        top_up = info.data["PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT"]
        if v < 2 * top_up:
            msg = "PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT (={v}) should be at least twice PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT ({top_up})"
            raise ValueError(msg)
        return v


def get_plugin_settings(app: web.Application) -> PaymentsSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_PAYMENTS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, PaymentsSettings)  # nosec
    return settings
