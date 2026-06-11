from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .. import Channel


class FromIdentity(StrEnum):
    SUPPORT = "support"
    NO_REPLY = "no-reply"


class EmailContact(BaseModel):
    name: str
    email: EmailStr


class EmailAttachment(BaseModel):
    content: bytes
    filename: str


class EmailContent(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=998)]
    body_html: str | None = None
    body_text: str | None = None


class EmailAddressing(BaseModel):
    from_identity: FromIdentity = FromIdentity.SUPPORT
    to: list[EmailContact]
    bcc: EmailContact | None = None
    reply_to: EmailContact | None = None

    attachments: list[EmailAttachment] | None = None

    model_config = ConfigDict(
        frozen=True,
    )


class EmailMessage(BaseModel):
    channel: Channel = Channel.email

    addressing: EmailAddressing
    content: EmailContent


type Addressing = EmailAddressing
type Message = EmailMessage
