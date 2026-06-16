from typing import Annotated, Self

from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from models_library.basic_types import LogLevel
from models_library.notifications.rpc import SenderIdentity
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.types import SecretStr
from settings_library.application import BaseApplicationSettings
from settings_library.basic_types import PortInt
from settings_library.celery import CelerySettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from ..models.smtp import ALLOWED_HEADERS, EmailProtocol


class SMTPSettings(BaseModel):
    """Settings for Simple Mail Transfer Protocol (SMTP)

    NOTE: These settings are only intended to login and access an email server.
    Extra info necessary to send an email such as sender email 'from' or 'reply-to' are now
    product-dependent and therefore can be found in the product table of the database
    """

    model_config = ConfigDict(frozen=True)

    host: str
    port: PortInt
    protocol: Annotated[
        EmailProtocol,
        Field(
            description="Select between TLS, STARTTLS Secure Mode or unencrypted communication",
        ),
    ] = EmailProtocol.UNENCRYPTED

    username: Annotated[str | None, Field(min_length=1)] = None
    password: Annotated[SecretStr | None, Field(min_length=1)] = None

    @model_validator(mode="after")
    def _both_credentials_must_be_set(self) -> Self:
        username = self.username
        password = self.password

        if (username is None and password) or (username and password is None):
            msg = f"Please provide both {username=} and {password=} not just one"
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def _enabled_tls_required_authentication(self) -> Self:
        protocol = self.protocol

        username = self.username
        password = self.password

        tls_enabled = protocol == EmailProtocol.TLS
        starttls_enabled = protocol == EmailProtocol.STARTTLS

        if (tls_enabled or starttls_enabled) and not (username or password):
            msg = "when using protocol other than UNENCRYPTED username and password are required"
            raise ValueError(msg)
        return self

    @property
    def has_credentials(self) -> bool:
        return self.username is not None and self.password is not None


class ProductSMTPSettings(BaseModel):
    """Per-product SMTP configuration referencing a named mail server profile."""

    model_config = {"frozen": True}

    mail_server: Annotated[
        str,
        Field(description="Name of the mail server profile from mail_servers dict"),
    ]
    domain: str
    local_parts: Annotated[
        dict[SenderIdentity, str],
        Field(
            description="A mapping of FromIdentity values to local-part strings used to build sender emails.",
            examples=[
                {
                    "support": "support",
                    "no_reply": "no-reply",
                }
            ],
        ),
    ]

    @model_validator(mode="after")
    def _validate_local_parts_complete(self) -> Self:
        missing = set(SenderIdentity) - set(self.local_parts)
        if missing:
            msg = f"local_parts is missing required identities: {sorted(missing)}. Required: {sorted(SenderIdentity)}"
            raise ValueError(msg)
        return self

    extra_headers: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            description="Extra headers to add to the email, e.g. {'X-Priority': '1 (Highest)'}",
        ),
    ] = DEFAULT_FACTORY

    @model_validator(mode="after")
    def _validate_extra_headers_allowed(self) -> Self:
        disallowed = {k for k in self.extra_headers if k.lower() not in ALLOWED_HEADERS}
        if disallowed:
            msg = (
                f"extra_headers contains non-permitted headers: {sorted(disallowed)}. "
                f"Allowed (case-insensitive): {sorted(ALLOWED_HEADERS)}"
            )
            raise ValueError(msg)
        return self


class NotificationsSMTPSettings(BaseModel):
    """Root model for SMTP settings with named mail server profiles and per-product config."""

    model_config = {"frozen": True}

    mail_servers: dict[str, SMTPSettings]
    products: dict[str, ProductSMTPSettings]

    @model_validator(mode="after")
    def _validate_mail_server_references(self) -> Self:
        for product_name, product_settings in self.products.items():
            if product_settings.mail_server not in self.mail_servers:
                msg = (
                    f"Product '{product_name}' references mail_server "
                    f"'{product_settings.mail_server}' which is not defined in mail_servers. "
                    f"Available: {sorted(self.mail_servers.keys())}"
                )
                raise ValueError(msg)
        return self

    def get_product_smtp_settings(self, product_name: str) -> ProductSMTPSettings:
        return self.products[product_name]

    def get_smtp_settings(self, product_name: str) -> SMTPSettings:
        product = self.products[product_name]
        return self.mail_servers[product.mail_server]


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
        NotificationsSMTPSettings | None,
        Field(
            description=(
                "Per-product SMTP settings with named mail server profiles and product-to-profile mapping. "
                "Required by the notifications worker; unused by the API service."
            ),
            examples=[
                {
                    "mail_servers": {
                        "aws": {
                            "host": "email-smtp.us-east-1.amazonaws.com",
                            "port": 465,
                            "protocol": "TLS",
                            "username": "AKIA...",
                            "password": "***",
                        }
                    },
                    "products": {
                        "osparc": {
                            "mail_server": "aws",
                            "domain": "sim4life.io",
                            "extra_headers": {},
                            "local_parts": {
                                "no_reply": "no-reply",
                                "support": "support",
                            },
                        }
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
