from enum import StrEnum
from typing import Annotated, Final, Self

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import model_validator
from pydantic.fields import Field
from pydantic.types import SecretStr
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings
from .basic_types import PortInt

ALLOWED_HEADERS: Final[frozenset[str]] = frozenset(
    {
        # AWS SES routing/configuration
        "x-ses-tenant",
        "x-ses-configuration-set",
        "x-ses-source-arn",
        "x-ses-from-arn",
        "x-ses-return-path-arn",
        # Delivery metadata (safe, non-structural)
        "return-path",
        "x-mailer",
        "x-priority",
        "precedence",
        "list-unsubscribe",
        "list-unsubscribe-post",
    }
)


class EmailProtocol(StrEnum):
    UNENCRYPTED = "UNENCRYPTED"
    TLS = "TLS"
    STARTTLS = "STARTTLS"


class SMTPLocals(BaseCustomSettings):
    SUPPORT: str
    NO_REPLY: str

    model_config = SettingsConfigDict(
        extra="ignore",
    )


class SMTPSettings(BaseCustomSettings):
    """Settings for Simple Mail Transfer Protocol (SMTP)

    NOTE: These settings are only intended to login and access an email server.
    Extra info necessary to send an email such as sender email 'from' or 'reply-to' are now
    product-dependent and therefore can be found in the product table of the database
    """

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
    extra_headers: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            description="Extra headers to add to the email, e.g. {'X-Priority': '1 (Highest)'}",
        ),
    ] = DEFAULT_FACTORY

    domain: str

    local_parts: Annotated[
        SMTPLocals,
        Field(
            default_factory=SMTPLocals,
            description=("A mapping of local email identifiers to actual email addresses."),
            examples=[
                {
                    "SUPPORT": "support",
                    "NO_REPLY": "no-reply",
                }
            ],
        ),
    ] = DEFAULT_FACTORY

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
            msg = "when using SMTP_PROTOCOL other than UNENCRYPTED username and password are required"
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

    @property
    def has_credentials(self) -> bool:
        return self.username is not None and self.password is not None
