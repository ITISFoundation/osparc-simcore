from enum import StrEnum
from typing import Annotated, Final, Self

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import model_validator
from pydantic.fields import Field
from pydantic.types import SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt

ALLOWED_HEADERS: Final = frozenset(
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


class SMTPSettings(BaseCustomSettings):
    """Settings for Simple Mail Transfer Protocol (SMTP)

    NOTE: These settings are only intended to login and access an email server.
    Extra info necessary to send an email such as sender email 'from' or 'reply-to' are now
    product-dependent and therefore can be found in the product table of the database
    """

    SMTP_HOST: str
    SMTP_PORT: PortInt
    SMTP_PROTOCOL: Annotated[
        EmailProtocol,
        Field(
            description="Select between TLS, STARTTLS Secure Mode or unencrypted communication",
        ),
    ] = EmailProtocol.UNENCRYPTED

    SMTP_USERNAME: Annotated[str | None, Field(min_length=1)] = None
    SMTP_PASSWORD: Annotated[SecretStr | None, Field(min_length=1)] = None
    SMTP_EXTRA_HEADERS: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            description="Extra headers to add to the email, e.g. {'X-Priority': '1 (Highest)'}",
        ),
    ] = DEFAULT_FACTORY

    @model_validator(mode="after")
    def _both_credentials_must_be_set(self) -> Self:
        username = self.SMTP_USERNAME
        password = self.SMTP_PASSWORD

        if (username is None and password) or (username and password is None):
            msg = f"Please provide both {username=} and {password=} not just one"
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def _enabled_tls_required_authentication(self) -> Self:
        smtp_protocol = self.SMTP_PROTOCOL

        username = self.SMTP_USERNAME
        password = self.SMTP_PASSWORD

        tls_enabled = smtp_protocol == EmailProtocol.TLS
        starttls_enabled = smtp_protocol == EmailProtocol.STARTTLS

        if (tls_enabled or starttls_enabled) and not (username or password):
            msg = "when using SMTP_PROTOCOL other than UNENCRYPTED username and password are required"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_extra_headers_allowed(self) -> Self:
        disallowed = {k for k in self.SMTP_EXTRA_HEADERS if k.lower() not in ALLOWED_HEADERS}
        if disallowed:
            msg = (
                f"SMTP_EXTRA_HEADERS contains non-permitted headers: {sorted(disallowed)}. "
                f"Allowed (case-insensitive): {sorted(ALLOWED_HEADERS)}"
            )
            raise ValueError(msg)
        return self

    @property
    def has_credentials(self) -> bool:
        return self.SMTP_USERNAME is not None and self.SMTP_PASSWORD is not None
