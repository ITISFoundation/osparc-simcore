"""Celery worker task payloads for notifications service."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..._notifications import ChannelType


class EmailContact(BaseModel):
    name: str = ""
    email: EmailStr


class EmailAttachment(BaseModel):
    content: bytes
    filename: str


class EmailContent(BaseModel):
    subject: Annotated[
        str,
        Field(
            min_length=1,
            # NOTE: RFC 2822 limit
            max_length=998,
        ),
    ]
    body_text: str | None = None
    body_html: str | None = None


class EmailMessage(BaseModel):
    """Email message with multiple recipients for bulk sending."""

    channel: ChannelType = ChannelType.email

    # Envelope fields
    from_: Annotated[EmailContact, Field(alias="from")]
    to: Annotated[list[EmailContact], Field(min_length=1)]
    reply_to: EmailContact | None = None
    cc: list[EmailContact] | None = None
    bcc: list[EmailContact] | None = None

    # Content fields
    content: EmailContent

    attachments: list[EmailAttachment] | None = None

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
    )
