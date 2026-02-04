from email.utils import parseaddr
from typing import Annotated, Self

from models_library.emails import LowerCaseEmailStr
from models_library.notifications import ChannelType
from pydantic import BaseModel, ConfigDict, Field


class EmailAddress(BaseModel):
    display_name: str = ""
    addr_spec: LowerCaseEmailStr

    @classmethod
    def from_email_str(cls, email_str: str) -> Self:
        display_name, addr_spec = parseaddr(email_str)
        return cls(display_name=display_name, addr_spec=addr_spec)

    def to_email_str(self) -> str:
        if self.display_name:
            return f"{self.display_name} <{self.addr_spec}>"
        return self.addr_spec

    model_config = ConfigDict(
        frozen=True,
    )


class EmailAttachment(BaseModel):
    content: bytes
    filename: str

    model_config = ConfigDict(
        frozen=True,
    )


class EmailContent(BaseModel):
    subject: str
    body_text: str
    body_html: str | None = None

    model_config = ConfigDict(
        frozen=True,
    )


class EmailNotificationMessage(BaseModel):
    channel: ChannelType = ChannelType.email

    from_: Annotated[EmailAddress, Field(alias="from")]
    to: list[EmailAddress]
    reply_to: EmailAddress | None = None
    bcc: list[EmailAddress] | None = None

    content: EmailContent

    attachments: list[EmailAttachment] | None = None

    model_config = ConfigDict(
        frozen=True,
        validate_by_alias=True,
        validate_by_name=True,
    )
