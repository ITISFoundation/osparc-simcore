from enum import Enum
from typing import Self

from pydantic import model_validator
from pydantic.fields import Field
from pydantic.types import SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class EmailProtocol(str, Enum):
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
    SMTP_PROTOCOL: EmailProtocol = Field(
        EmailProtocol.UNENCRYPTED,
        description="Select between TLS, STARTTLS Secure Mode or unencrypted communication",
    )
    SMTP_USERNAME: str | None = Field(None, min_length=1)
    SMTP_PASSWORD: SecretStr | None = Field(None, min_length=1)

    @model_validator(mode="after")
    def _both_credentials_must_be_set(self) -> Self:
        username = self.SMTP_USERNAME
        password = self.SMTP_PASSWORD

        if username is None and password or username and password is None:
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

    @property
    def has_credentials(self) -> bool:
        return self.SMTP_USERNAME is not None and self.SMTP_PASSWORD is not None
