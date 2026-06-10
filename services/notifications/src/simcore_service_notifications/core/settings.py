from typing import Annotated

from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from models_library.basic_types import LogLevel
from models_library.products import ProductName
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    field_validator,
    model_validator,
)
from settings_library.application import BaseApplicationSettings
from settings_library.celery import CelerySettings
from settings_library.email import SMTPSettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

type ProfileName = str


class _ProductSMTPSettings(BaseModel):
    """Per-product SMTP configuration with named profiles."""

    model_config = {"frozen": True}

    smtp_profiles: dict[ProfileName, SMTPSettings]
    product_to_profile: dict[ProductName, ProfileName]

    @model_validator(mode="after")
    def _all_profiles_exist(self) -> "_ProductSMTPSettings":
        missing = {profile for profile in self.product_to_profile.values() if profile not in self.smtp_profiles}
        if missing:
            msg = f"product_to_profile references undefined SMTP profiles: {sorted(missing)}"
            raise ValueError(msg)
        return self

    def get_settings_for_product(self, product_name: ProductName) -> SMTPSettings:
        profile_name = self.product_to_profile.get(product_name)
        if profile_name is None:
            msg = f"No SMTP profile configured for product {product_name!r}"
            raise ValueError(msg)
        return self.smtp_profiles[profile_name]


class ApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    LOG_LEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices(
                "NOTIFICATIONS_LOGLEVEL",
                "LOG_LEVEL",
                "LOGLEVEL",
            ),
        ),
    ] = LogLevel.WARNING

    NOTIFICATIONS_CELERY: Annotated[
        CelerySettings | None,
        Field(
            description="Settings for Celery",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    NOTIFICATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "NOTIFICATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED",
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description=(
                "Enables local development log format. WARNING: make sure it is "
                "disabled if you want to have structured logs!"
            ),
        ),
    ] = False

    NOTIFICATIONS_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices("NOTIFICATIONS_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"),
            description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') "
            "to a list of log message patterns that should be filtered out.",
        ),
    ] = DEFAULT_FACTORY

    NOTIFICATIONS_RABBITMQ: Annotated[
        RabbitSettings,
        Field(
            description="settings for service/rabbitmq",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    NOTIFICATIONS_POSTGRES: Annotated[
        PostgresSettings,
        Field(
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    NOTIFICATIONS_TRACING: Annotated[
        TracingSettings | None,
        Field(
            description="settings for opentelemetry tracing",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    NOTIFICATIONS_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True

    NOTIFICATIONS_WORKER_MODE: Annotated[bool, Field(description="If True, run as a worker")] = False

    NOTIFICATIONS_EMAIL_MAX_RECIPIENTS_PER_MESSAGE: Annotated[
        int,
        Field(description="Maximum number of recipients per email message"),
    ] = 20

    NOTIFICATIONS_EMAIL_RATE_LIMIT: Annotated[
        str,
        Field(description="Rate limit for sending emails, e.g. '0.2/s' means 1 email every 5 seconds"),
    ] = "1/s"

    NOTIFICATIONS_SMTP_SETTINGS: Annotated[
        _ProductSMTPSettings | None,
        Field(
            description=(
                "Per-product SMTP settings with named profiles and product-to-profile mapping. "
                "Required by the notifications worker; unused by the API service."
            ),
            examples=[
                {
                    "smtp_profiles": {
                        "aws_ses_sim4life": {
                            "SMTP_HOST": "email-smtp.us-east-1.amazonaws.com",
                            "SMTP_PORT": 465,
                            "SMTP_PROTOCOL": "TLS",
                            "SMTP_USERNAME": "AKIA...",
                            "SMTP_PASSWORD": "secret",
                            "SMTP_DOMAIN": "sim4life.io",
                            "SMTP_LOCAL_PARTS": {
                                "NO_REPLY": "no-reply",
                                "SUPPORT": "support",
                            },
                        },
                        "postal_osparc": {
                            "SMTP_HOST": "smtp.osparc.io",
                            "SMTP_PORT": 25,
                            "SMTP_PROTOCOL": "UNENCRYPTED",
                            "SMTP_DOMAIN": "osparc.io",
                            "SMTP_LOCAL_PARTS": {
                                "NO_REPLY": "no-reply",
                                "SUPPORT": "support",
                            },
                        },
                    },
                    "product_to_profile": {
                        "s4l": "aws_ses_sim4life",
                        "osparc": "postal_osparc",
                    },
                }
            ],
        ),
    ] = None

    @field_validator("LOG_LEVEL")
    @classmethod
    def valid_log_level(cls, value) -> LogLevel:
        return LogLevel(cls.validate_log_level(value))

    @model_validator(mode="after")
    def _worker_requires_smtp_settings(self) -> "ApplicationSettings":
        if self.NOTIFICATIONS_WORKER_MODE and self.NOTIFICATIONS_SMTP_SETTINGS is None:
            msg = (
                "NOTIFICATIONS_SMTP_SETTINGS must be configured when "
                "NOTIFICATIONS_WORKER_MODE is enabled "
                "(per-product SMTP settings are required by the worker)."
            )
            raise ValueError(msg)
        return self
