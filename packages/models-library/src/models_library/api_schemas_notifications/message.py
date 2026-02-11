from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models_library.notifications import ChannelType


class EmailNotificationMessageAddress(BaseModel):
    name: str = ""
    email: EmailStr


class EmailNotificationMessageAttachment(BaseModel):
    content: bytes
    filename: str


class EmailNotificationMessageContent(BaseModel):
    subject: Annotated[
        str,
        Field(
            min_length=1,
            max_length=998,  # RFC 2822 limit
        ),
    ]
    body_text: str
    body_html: str | None = None


class EmailNotificationMessage(BaseModel):
    channel: ChannelType = ChannelType.email

    # Envelope fields
    from_: Annotated[EmailNotificationMessageAddress, Field(alias="from")]
    to: Annotated[list[EmailNotificationMessageAddress], Field(min_length=1)]
    reply_to: EmailNotificationMessageAddress | None = None
    cc: list[EmailNotificationMessageAddress] | None = None
    bcc: list[EmailNotificationMessageAddress] | None = None

    # Content fields
    content: EmailNotificationMessageContent

    attachments: list[EmailNotificationMessageAttachment] | None = None

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
    )
