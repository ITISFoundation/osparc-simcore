from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models_library.notifications import ChannelType


class EmailContact(BaseModel):
    name: str | None = None
    email: EmailStr


class EmailAttachment(BaseModel):
    content: bytes
    filename: str


class EmailContent(BaseModel):
    subject: str
    body_text: str
    body_html: str


class EmailMessage(BaseModel):
    channel: ChannelType = ChannelType.email

    from_: Annotated[EmailContact, Field(alias="from")]
    to: list[EmailContact]
    reply_to: EmailContact | None = None
    bcc: list[EmailContact] | None = None

    content: EmailContent

    attachments: list[EmailAttachment] | None = None

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
    )
