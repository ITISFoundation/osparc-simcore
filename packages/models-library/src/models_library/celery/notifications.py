"""Celery worker task payloads for notifications service."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..notifications import ChannelType


class EmailAddress(BaseModel):
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
    body_text: str
    body_html: str | None = None


class EmailMessage(BaseModel):
    """Email message with multiple recipients for bulk sending."""

    channel: ChannelType = ChannelType.email

    # Envelope fields
    from_: Annotated[EmailAddress, Field(alias="from")]
    to: Annotated[list[EmailAddress], Field(min_length=1)]
    reply_to: EmailAddress | None = None
    cc: list[EmailAddress] | None = None
    bcc: list[EmailAddress] | None = None

    # Content fields
    content: EmailContent

    attachments: list[EmailAttachment] | None = None

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
    )


class SingleEmailMessage(BaseModel):
    """Payload for single email Celery task (one recipient per task)."""

    from_: Annotated[EmailAddress, Field(alias="from")]
    to: EmailAddress
    reply_to: EmailAddress | None = None

    content: EmailContent

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
    )
