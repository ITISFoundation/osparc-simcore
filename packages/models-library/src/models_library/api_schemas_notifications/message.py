from typing import Annotated

from pydantic import BaseModel, EmailStr, Field


class EmailAddress(BaseModel):
    display_name: str
    addr_spec: EmailStr


class EmailAttachment(BaseModel):
    content: bytes
    filename: str


class EmailContent(BaseModel):
    subject: str
    body_text: str
    body_html: str | None = None


class EmailNotificationMessage(BaseModel):
    channel: str = "email"

    from_: Annotated[EmailAddress, Field(alias="from")]
    to: EmailAddress
    reply_to: EmailAddress | None = None

    content: EmailContent

    attachments: list[EmailAttachment] | None = None
