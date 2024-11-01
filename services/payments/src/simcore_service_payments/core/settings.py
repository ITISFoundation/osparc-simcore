from functools import cached_property

from models_library.basic_types import NonNegativeDecimal
from pydantic import (
    EmailStr,
    Field,
    HttpUrl,
    PositiveFloat,
    SecretStr,
    parse_obj_as,
    validator,
)
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.application import BaseApplicationSettings
from settings_library.basic_types import LogLevel, VersionTag
from settings_library.email import SMTPSettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME


class _BaseApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    """Base settings of any osparc service's app"""

    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = PROJECT_NAME
    API_VTAG: VersionTag = parse_obj_as(VersionTag, API_VTAG)

    # RUNTIME  -----------------------------------------------------------

    PAYMENTS_LOGLEVEL: LogLevel = Field(
        default=LogLevel.INFO, env=["PAYMENTS_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )
    PAYMENTS_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "PAYMENTS_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    PAYMENTS_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        env=["PAYMENTS_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"],
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )

    @cached_property
    def LOG_LEVEL(self):  # noqa: N802
        return self.PAYMENTS_LOGLEVEL

    @validator("PAYMENTS_LOGLEVEL", pre=True)
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


class ApplicationSettings(_BaseApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    PAYMENTS_GATEWAY_URL: HttpUrl = Field(
        ..., description="Base url to the payment gateway"
    )

    PAYMENTS_GATEWAY_API_SECRET: SecretStr = Field(
        ..., description="Credentials for payments-gateway api"
    )

    PAYMENTS_USERNAME: str = Field(
        ...,
        description="Username for Auth. Required if started as a web app.",
        min_length=3,
    )
    PAYMENTS_PASSWORD: SecretStr = Field(
        ...,
        description="Password for Auth. Required if started as a web app.",
        min_length=10,
    )

    PAYMENTS_ACCESS_TOKEN_SECRET_KEY: SecretStr = Field(
        ...,
        description="To generate a random password with openssl in hex format with 32 bytes, run `openssl rand -hex 32`",
        min_length=30,
    )
    PAYMENTS_ACCESS_TOKEN_EXPIRE_MINUTES: PositiveFloat = Field(default=30)

    PAYMENTS_AUTORECHARGE_MIN_BALANCE_IN_CREDITS: NonNegativeDecimal = Field(
        default=100,
        description="Minimum balance in credits to top-up for auto-recharge",
    )

    PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT: NonNegativeDecimal = Field(
        default=100,
        description="Default value in USD on the amount to top-up for auto-recharge (`top_up_amount_in_usd`)",
    )

    PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT: NonNegativeDecimal | None = Field(
        default=10000,
        description="Default value in USD for the montly limit for auto-recharge (`monthly_limit_in_usd`)",
    )
    PAYMENTS_AUTORECHARGE_ENABLED: bool = Field(
        default=False,
        description="Based on this variable is the auto recharge functionality in Payment service enabled",
    )

    PAYMENTS_BCC_EMAIL: EmailStr | None = Field(
        default=None,
        description="Special email for finance department. Currently used to BCC invoices.",
    )

    PAYMENTS_RABBITMQ: RabbitSettings = Field(
        auto_default_from_env=True, description="settings for service/rabbitmq"
    )

    PAYMENTS_TRACING: TracingSettings | None = Field(
        auto_default_from_env=True, description="settings for opentelemetry tracing"
    )

    PAYMENTS_POSTGRES: PostgresSettings = Field(
        auto_default_from_env=True, description="settings for postgres service"
    )

    PAYMENTS_STRIPE_URL: HttpUrl = Field(
        ..., description="Base url to the payment Stripe"
    )
    PAYMENTS_STRIPE_API_SECRET: SecretStr = Field(
        ..., description="Credentials for Stripe api"
    )

    PAYMENTS_SWAGGER_API_DOC_ENABLED: bool = Field(
        default=True, description="If true, it displays swagger doc at /doc"
    )

    PAYMENTS_RESOURCE_USAGE_TRACKER: ResourceUsageTrackerSettings = Field(
        auto_default_from_env=True, description="settings for RUT service"
    )

    PAYMENTS_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True

    PAYMENTS_EMAIL: SMTPSettings | None = Field(
        auto_default_from_env=True,
        description="optional email (see notifier_email service)",
    )
