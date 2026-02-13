from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, EmailStr, Field


class ChannelType(StrEnum):
    email = "email"


type TemplateName = Annotated[str, Field(min_length=1)]


class TemplateRef(BaseModel):
    channel: ChannelType
    template_name: TemplateName


class EmailContact(BaseModel):
    name: str
    email: EmailStr


class EmailMessageContentBody(BaseModel):
    html: str | None = None
    text: str | None = None


class EmailMessageContent(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=998)]
    body: EmailMessageContentBody


type NotificationsMessageContent = (
    EmailMessageContent
    # add here other channel contents (e.g. | SMSNotificationsContent)
)


class NotificationsMessage(BaseModel):
    channel: ChannelType


class EmailMessage(NotificationsMessage):
    channel: ChannelType = ChannelType.email
    from_: Annotated[EmailContact, Field(alias="from")]
    to: list[EmailContact]
    content: EmailMessageContent


class TemplatePreview(BaseModel):
    ref: TemplateRef
    message_content: dict[str, Any]
