from enum import Enum
from typing import Annotated, Self

from common_library.basic_types import DEFAULT_FACTORY
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
    def _extra_headers_must_start_with_x(self) -> Self:
        for key in self.SMTP_EXTRA_HEADERS:
            if not key.lower().startswith("x-"):
                msg = f"Extra header key '{key}' must start with 'X-' or 'x-'"
                raise ValueError(msg)
        return self

    @property
    def has_credentials(self) -> bool:
        return self.SMTP_USERNAME is not None and self.SMTP_PASSWORD is not None
