from typing import Annotated

from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from common_library.network import extract_email_domain
from models_library.basic_types import LogLevel
from pydantic import AliasChoices, Field, RootModel, StringConstraints, field_validator
from settings_library.application import BaseApplicationSettings
from settings_library.celery import CelerySettings
from settings_library.email import SMTPSettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

type Domain = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _PerDomainSMTPSettings(RootModel[dict[Domain, SMTPSettings]]):
    """SMTP settings keyed by sender email domain. Keys are normalized to lowercase."""

    @field_validator("root", mode="after")
    @classmethod
    def _normalize_keys(cls, value: dict[Domain, SMTPSettings]) -> dict[Domain, SMTPSettings]:
        normalized = {key.strip().lower(): settings for key, settings in value.items()}
        if len(normalized) != len(value):
            msg = f"Duplicate domains after case-normalization: {sorted(value)}"
            raise ValueError(msg)
        return normalized

    def for_email(self, email: str) -> SMTPSettings:
        domain = extract_email_domain(email).lower()
        settings = self.root.get(domain)
        if settings is None:
            msg = f"No SMTP settings configured for domain {domain!r} (from={email!r})"
            raise ValueError(msg)
        return settings


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

    NOTIFICATIONS_EMAIL: Annotated[
        _PerDomainSMTPSettings | None,
        Field(
            description=(
                "Per-domain SMTP settings keyed by sender email domain (e.g. 'osparc.io'). "
                "Configured as JSON env, e.g. "
                '{"osparc.io": {"SMTP_HOST": "smtp.osparc.io", "SMTP_PORT": 25, ...}}. '
                "Required by the notifications worker; unused by the API service."
            ),
        ),
    ] = None

    @field_validator("LOG_LEVEL")
    @classmethod
    def valid_log_level(cls, value) -> LogLevel:
        return LogLevel(cls.validate_log_level(value))
