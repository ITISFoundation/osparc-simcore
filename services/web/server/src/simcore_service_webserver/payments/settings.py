import os
from functools import cached_property

from aiohttp import web
from pydantic import Field, HttpUrl, PositiveInt, SecretStr, parse_obj_as, validator
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
    PAYMENTS_VTAG: VersionTag = parse_obj_as(VersionTag, "v1")

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
    PAYMENTGS_PLUGIN_ENABLED: bool = Field(
        default=True,
    )

    PAYMENTS_FAKE_COMPLETION: bool = Field(
        default=False, description="Enables fake completion. ONLY for testing purposes"
    )

    PAYMENTS_FAKE_COMPLETION_DELAY_SEC: PositiveInt = Field(
        default=10,
        description="Delay in seconds sbefore completion. ONLY for testing purposes",
    )

    PAYMENTS_FAKE_GATEWAY_URL: HttpUrl = Field(
        default=parse_obj_as(HttpUrl, "https://fake-payment-gateway.com"),
        description="FAKE Base url to the payment gateway",
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

    @validator("PAYMENTS_FAKE_COMPLETION")
    @classmethod
    def check_dev_feature_enabled(cls, v):
        if v and not os.environ.get("WEBSERVER_DEV_FEATURES_ENABLED", False):
            msg = "PAYMENTS_FAKE_COMPLETION only allowed when WEBSERVER_DEV_FEATURES_ENABLED=1"
            raise ValueError(msg)
        return v


def get_plugin_settings(app: web.Application) -> PaymentsSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_PAYMENTS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, PaymentsSettings)  # nosec
    return settings
