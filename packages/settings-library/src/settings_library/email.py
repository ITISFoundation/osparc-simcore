from typing import Optional
from pydantic import root_validator

from pydantic.fields import Field
from pydantic.types import SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class SMTPSettings(BaseCustomSettings):
    """Simple Mail Transfer Protocol"""

    SMTP_SENDER: str = "@".join(["O2SPARC support <support", "osparc.io>"])

    SMTP_HOST: str
    SMTP_PORT: PortInt

    SMTP_TLS_ENABLED: bool = Field(False, description="Enables Secure Mode")
    SMTP_USERNAME: Optional[str]
    SMTP_PASSWORD: Optional[SecretStr]

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
        tls_enabled = values.get("SMTP_TLS_ENABLED")
        username = values.get("SMTP_USERNAME")
        password = values.get("SMTP_PASSWORD")

        if tls_enabled and not (username or password):
            raise ValueError(
                "when using SMTP_TLS_ENABLED is True username and password are required"
            )
        return values
