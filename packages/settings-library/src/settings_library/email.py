from pydantic.fields import Field
from pydantic.types import SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class SMTPSettings(BaseCustomSettings):
    """Simple Mail Transfer Protocol"""

    SMTP_SENDER: str = "@".join(["O2SPARC support <support", "osparc.io>"])

    SMTP_HOST: str
    SMTP_PORT: PortInt

    SMTP_TLS_ENABLED: bool = Field(description="Enables Secure Mode")
    SMTP_USERNAME: str
    SMTP_PASSWORD: SecretStr
