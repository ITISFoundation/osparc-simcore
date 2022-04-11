from enum import Enum
from typing import Optional

from pydantic import root_validator
from pydantic.fields import Field
from pydantic.types import SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class EmailProtocol(str, Enum):
    UNENCRYPTED = "UNENCRYPTED"
    TLS = "TLS"
    STARTTLS = "STARTTLS"


class SMTPSettings(BaseCustomSettings):
    """Simple Mail Transfer Protocol"""

    # TODO: NameEmail or EmailStr
    SMTP_SENDER: str = "@".join(["O2SPARC support <support", "osparc.io>"])

    SMTP_HOST: str
    SMTP_PORT: PortInt

    SMTP_PROTOCOL: EmailProtocol = Field(
        EmailProtocol.UNENCRYPTED,
        description="Select between TLS, STARTTLS Secure Mode or unencrypted communication",
    )
    SMTP_USERNAME: Optional[str] = Field(None, min_length=1)
    SMTP_PASSWORD: Optional[SecretStr] = Field(None, min_length=1)

    @root_validator
    @classmethod
    def both_credentials_must_be_set(cls, values):
        username = values.get("SMTP_USERNAME")
        password = values.get("SMTP_PASSWORD")

        if username is None and password or username and password is None:
            raise ValueError(
                f"Please provide both {username=} and {password=} not just one"
            )

        return values

    @root_validator
    @classmethod
    def enabled_tls_required_authentication(cls, values):
        smtp_protocol = values.get("SMTP_PROTOCOL")

        username = values.get("SMTP_USERNAME")
        password = values.get("SMTP_PASSWORD")

        tls_enabled = smtp_protocol == EmailProtocol.TLS
        starttls_enabled = smtp_protocol == EmailProtocol.STARTTLS

        if (tls_enabled or starttls_enabled) and not (username or password):
            raise ValueError(
                "when using SMTP_PROTOCOL other than UNENCRYPTED username and password are required"
            )
        return values
