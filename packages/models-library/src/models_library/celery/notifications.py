"""Celery worker task payloads for notifications service."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from ..notifications import ChannelType


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

    @model_validator(mode="after")
    def _ensure_at_least_one_body_format(self) -> Self:
        if not self.body_text and not self.body_html:
            msg = "At least one of body_text or body_html must be provided."
            raise ValueError(msg)
        return self


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


class SingleEmailMessage(BaseModel):
    """Payload for single email Celery task (one recipient per task)."""

    from_: Annotated[EmailContact, Field(alias="from")]
    to: EmailContact
    reply_to: EmailContact | None = None

    content: EmailContent

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
    )


type Message = EmailMessage
