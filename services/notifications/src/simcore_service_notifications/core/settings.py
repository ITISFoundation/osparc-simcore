import re
from typing import Annotated, Final, Self

from annotated_types import doc
from celery_library.basic_types import BootServerMode
from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from models_library.basic_regex import TWILIO_ALPHANUMERIC_SENDER_ID_RE
from models_library.basic_types import LogLevel
from models_library.notifications import Channel
from models_library.notifications.errors import (
    NotificationsProductSMTPSettingsNotFoundError,
    NotificationsProductTwilioSettingsNotFoundError,
)
from models_library.notifications.rpc import SenderIdentity
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.types import SecretStr
from servicelib.celery.async_jobs.notifications import (
    channel_from_notifications_queue_name,
    notifications_queue_name,
)
from settings_library.application import BaseApplicationSettings
from settings_library.basic_types import PortInt
from settings_library.celery import CelerySettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.tracing import TracingSettings
from settings_library.twilio import TwilioSettings
from settings_library.utils_logging import MixinLoggingSettings

from ..exceptions.errors import InvalidNotificationsChannelSettingsError
from ..models.smtp import ALLOWED_HEADERS, EmailProtocol

_CHANNEL_REQUIRED_SETTINGS: Final[
    Annotated[
        dict[Channel, str],
        doc(
            "settings field each consumed channel requires: without it a worker boots "
            "and only fails once a task of that channel runs"
        ),
    ]
] = {
    Channel.email: "NOTIFICATIONS_SMTP_SETTINGS",
    Channel.sms: "NOTIFICATIONS_TWILIO_SETTINGS",
}


class SMTPSettings(BaseModel):
    """Settings for Simple Mail Transfer Protocol (SMTP)

    NOTE: These settings are only intended to login and access an email server.
    Extra info necessary to send an email such as sender email 'from' or 'reply-to' are now
    product-dependent and resolved from NOTIFICATIONS_SMTP_SETTINGS (per-product 'domain',
    'local_parts' and 'extra_headers'), see NotificationsSMTPSettings/ProductSMTPSettings
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

    model_config = ConfigDict(frozen=True)

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
    extra_headers: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            description="Extra headers to add to the email, e.g. {'X-Priority': '1 (Highest)'}",
        ),
    ] = DEFAULT_FACTORY

    @model_validator(mode="after")
    def _validate_local_parts_complete(self) -> Self:
        missing = set(SenderIdentity) - set(self.local_parts)
        if missing:
            msg = f"local_parts is missing required identities: {sorted(missing)}. Required: {sorted(SenderIdentity)}"
            raise ValueError(msg)
        return self

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

    model_config = ConfigDict(frozen=True)

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
        if product_name not in self.products:
            raise NotificationsProductSMTPSettingsNotFoundError(product_name=product_name)
        return self.products[product_name]

    def get_smtp_settings(self, product_name: str) -> SMTPSettings:
        product = self.get_product_smtp_settings(product_name)
        return self.mail_servers[product.mail_server]


class ProductTwilioSettings(BaseModel):
    """Per-product Twilio configuration referencing a named account profile."""

    model_config = ConfigDict(frozen=True)

    account: Annotated[
        str,
        Field(description="Name of the twilio account profile from accounts dict"),
    ]
    messaging_service_sid: Annotated[str, Field(description="Twilio Messaging Service SID")]
    alphanumeric_sender_id: Annotated[
        str,
        Field(pattern=re.compile(TWILIO_ALPHANUMERIC_SENDER_ID_RE)),
    ]


class NotificationsTwilioSettings(BaseModel):
    """Root model for Twilio settings with named account profiles and per-product config."""

    model_config = ConfigDict(frozen=True)

    accounts: dict[str, TwilioSettings]
    products: dict[str, ProductTwilioSettings]

    @model_validator(mode="after")
    def _validate_account_references(self) -> Self:
        for product_name, product_settings in self.products.items():
            if product_settings.account not in self.accounts:
                msg = (
                    f"Product '{product_name}' references account "
                    f"'{product_settings.account}' which is not defined in accounts. "
                    f"Available: {sorted(self.accounts.keys())}"
                )
                raise ValueError(msg)
        return self

    def get_product_twilio_settings(self, product_name: str) -> ProductTwilioSettings:
        if product_name not in self.products:
            raise NotificationsProductTwilioSettingsNotFoundError(product_name=product_name)
        return self.products[product_name]

    def get_twilio_account_settings(self, product_name: str) -> TwilioSettings:
        product = self.get_product_twilio_settings(product_name)
        return self.accounts[product.account]


_CHANNEL_SETTINGS_MODELS: Final[dict[str, type[BaseModel]]] = {
    "NOTIFICATIONS_TWILIO_SETTINGS": NotificationsTwilioSettings,
    "NOTIFICATIONS_SMTP_SETTINGS": NotificationsSMTPSettings,
}


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

    NOTIFICATIONS_BOOT_SERVER_MODE: Annotated[
        BootServerMode,
        Field(description="Boot mode: REST API server or Celery worker"),
    ] = BootServerMode.AS_REST_API_SERVER

    NOTIFICATIONS_CELERY_QUEUES: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated queues consumed when booting as Celery worker, e.g. "
                "'notifications-email'. Passed to the Celery CLI by docker/boot.sh and "
                "checked against the per-channel settings at boot. When unset, the "
                "worker is assumed to consume the email channel."
            ),
        ),
    ] = None

    NOTIFICATIONS_EMAIL_MAX_RECIPIENTS_PER_MESSAGE: Annotated[
        int,
        Field(description="Maximum number of recipients per email message"),
    ] = 20

    NOTIFICATIONS_SMS_MAX_RECIPIENTS_PER_MESSAGE: Annotated[
        int,
        Field(description="Maximum number of recipients per sms message"),
    ] = 20

    NOTIFICATIONS_EMAIL_RATE_LIMIT: Annotated[
        str,
        Field(description="Rate limit for sending emails, e.g. '0.2/s' means 1 email every 5 seconds"),
    ] = "1/s"

    NOTIFICATIONS_SMS_RATE_LIMIT: Annotated[
        str,
        Field(description="Rate limit for sending sms, e.g. '0.2/s' means 1 sms every 5 seconds"),
    ] = "1/s"

    NOTIFICATIONS_TWILIO_SETTINGS: Annotated[
        NotificationsTwilioSettings | None,
        Field(
            description=(
                "Per-product Twilio settings with named account profiles and product-to-profile mapping. "
                "Used by the worker to deliver sms."
            ),
            examples=[
                {
                    "accounts": {
                        "main": {
                            "TWILIO_ACCOUNT_SID": "AC...",
                            "TWILIO_AUTH_TOKEN": "***",
                            "TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT": ["41"],
                        }
                    },
                    "products": {
                        "osparc": {
                            "account": "main",
                            "messaging_service_sid": "MG...",
                            "alphanumeric_sender_id": "osparc",
                        }
                    },
                }
            ],
        ),
    ] = None

    NOTIFICATIONS_SMTP_SETTINGS: Annotated[
        NotificationsSMTPSettings | None,
        Field(
            description=(
                "Per-product SMTP settings with named mail server profiles and product-to-profile mapping. "
                "Used by the API service to resolve sender identities when preparing messages, "
                "and by the worker to deliver emails."
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

    @field_validator("NOTIFICATIONS_TWILIO_SETTINGS", "NOTIFICATIONS_SMTP_SETTINGS", mode="before")
    @classmethod
    def _parse_channel_settings(cls, value, info: ValidationInfo) -> BaseModel | None:
        # a blank env var (e.g. an unset passthrough `${SMTP_SETTINGS}`) means unset; a
        # malformed value is reported by field name and reason only: pydantic echoes the
        # offending input in ValidationError, which here contains credentials
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        assert info.field_name is not None  # nosec
        model = _CHANNEL_SETTINGS_MODELS[info.field_name]
        try:
            if isinstance(value, str):
                return model.model_validate_json(value)
            return model.model_validate(value)
        except ValidationError as exc:
            reasons = "; ".join(f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors())
            # non-ValueError on purpose: pydantic wraps ValueError/AssertionError
            # and echoes the offending input, which here holds credentials
            raise InvalidNotificationsChannelSettingsError(env_name=info.field_name, errors=reasons) from None

    @field_validator("LOG_LEVEL")
    @classmethod
    def valid_log_level(cls, value) -> LogLevel:
        return LogLevel(cls.validate_log_level(value))

    @model_validator(mode="after")
    def _worker_requires_channel_settings(self) -> Self:
        if self.NOTIFICATIONS_BOOT_SERVER_MODE is not BootServerMode.AS_CELERY_WORKER:
            return self

        if self.NOTIFICATIONS_CELERY_QUEUES:
            queue_names = [name.strip() for name in self.NOTIFICATIONS_CELERY_QUEUES.split(",") if name.strip()]
        else:
            queue_names = [notifications_queue_name(Channel.email)]

        for channel in sorted({channel_from_notifications_queue_name(name) for name in queue_names}):
            required_field = _CHANNEL_REQUIRED_SETTINGS.get(channel)
            if required_field is None:
                msg = (
                    f"NOTIFICATIONS_CELERY_QUEUES consumes the '{channel}' channel "
                    f"({notifications_queue_name(channel)}) but this service version "
                    f"does not support delivering it."
                )
                raise ValueError(msg)
            if getattr(self, required_field) is None:
                msg = (
                    f"{required_field} must be configured when "
                    f"NOTIFICATIONS_BOOT_SERVER_MODE is AS_CELERY_WORKER and the worker "
                    f"consumes the '{channel}' channel (see NOTIFICATIONS_CELERY_QUEUES)."
                )
                raise ValueError(msg)
        return self
