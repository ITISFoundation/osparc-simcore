from decimal import Decimal
from functools import cached_property
from typing import Annotated, cast

from common_library.basic_types import DEFAULT_FACTORY
from models_library.basic_types import NonNegativeDecimal
from pydantic import (
    AliasChoices,
    EmailStr,
    Field,
    HttpUrl,
    PositiveFloat,
    SecretStr,
    TypeAdapter,
    field_validator,
)
from servicelib.logging_utils import LogLevelInt
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
    API_VTAG: VersionTag = TypeAdapter(VersionTag).validate_python(API_VTAG)

    # RUNTIME  -----------------------------------------------------------

    PAYMENTS_LOGLEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices("PAYMENTS_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"),
        ),
    ] = LogLevel.INFO

    PAYMENTS_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "LOG_FORMAT_LOCAL_DEV_ENABLED", "PAYMENTS_LOG_FORMAT_LOCAL_DEV_ENABLED"
            ),
            description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
        ),
    ] = False

    PAYMENTS_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices(
                "LOG_FILTER_MAPPING", "PAYMENTS_LOG_FILTER_MAPPING"
            ),
            description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
        ),
    ] = DEFAULT_FACTORY

    @cached_property
    def log_level(self) -> LogLevelInt:
        return cast(LogLevelInt, self.PAYMENTS_LOGLEVEL)

    @field_validator("PAYMENTS_LOGLEVEL", mode="before")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


class ApplicationSettings(_BaseApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    PAYMENTS_GATEWAY_URL: Annotated[
        HttpUrl, Field(description="Base url to the payment gateway")
    ]

    PAYMENTS_GATEWAY_API_SECRET: Annotated[
        SecretStr, Field(description="Credentials for payments-gateway api")
    ]

    PAYMENTS_USERNAME: Annotated[
        str,
        Field(
            description="Username for Auth. Required if started as a web app.",
            min_length=3,
        ),
    ]
    PAYMENTS_PASSWORD: Annotated[
        SecretStr,
        Field(
            description="Password for Auth. Required if started as a web app.",
            min_length=10,
        ),
    ]

    PAYMENTS_ACCESS_TOKEN_SECRET_KEY: Annotated[
        SecretStr,
        Field(
            description="To generate a random password with openssl in hex format with 32 bytes, run `openssl rand -hex 32`",
            min_length=30,
        ),
    ]
    PAYMENTS_ACCESS_TOKEN_EXPIRE_MINUTES: PositiveFloat = 30.0

    PAYMENTS_AUTORECHARGE_MIN_BALANCE_IN_CREDITS: Annotated[
        NonNegativeDecimal,
        Field(
            description="Minimum balance in credits to top-up for auto-recharge",
        ),
    ] = Decimal(100)

    PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT: Annotated[
        NonNegativeDecimal,
        Field(
            description="Default value in USD on the amount to top-up for auto-recharge (`top_up_amount_in_usd`)",
        ),
    ] = Decimal(100)

    PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT: Annotated[
        NonNegativeDecimal | None,
        Field(
            description="Default value in USD for the montly limit for auto-recharge (`monthly_limit_in_usd`)",
        ),
    ] = Decimal(10_000)

    PAYMENTS_AUTORECHARGE_ENABLED: Annotated[
        bool,
        Field(
            description="Based on this variable is the auto recharge functionality in Payment service enabled",
        ),
    ] = False

    PAYMENTS_BCC_EMAIL: Annotated[
        EmailStr | None,
        Field(
            description="Special email for finance department. Currently used to BCC invoices.",
        ),
    ] = None

    PAYMENTS_RABBITMQ: Annotated[
        RabbitSettings,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="settings for service/rabbitmq",
        ),
    ]

    PAYMENTS_TRACING: Annotated[
        TracingSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="settings for opentelemetry tracing",
        ),
    ]

    PAYMENTS_POSTGRES: Annotated[
        PostgresSettings,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="settings for postgres service",
        ),
    ]

    PAYMENTS_STRIPE_URL: Annotated[
        HttpUrl, Field(description="Base url to the payment Stripe")
    ]
    PAYMENTS_STRIPE_API_SECRET: Annotated[
        SecretStr, Field(description="Credentials for Stripe api")
    ]

    PAYMENTS_SWAGGER_API_DOC_ENABLED: Annotated[
        bool, Field(description="If true, it displays swagger doc at /doc")
    ] = True

    PAYMENTS_RESOURCE_USAGE_TRACKER: Annotated[
        ResourceUsageTrackerSettings,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="settings for RUT service",
        ),
    ]

    PAYMENTS_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True

    PAYMENTS_EMAIL: Annotated[
        SMTPSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="optional email (see notifier_email service)",
        ),
    ]
