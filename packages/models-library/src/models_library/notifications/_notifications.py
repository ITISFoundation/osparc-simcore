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


class EmailMessageContent(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=998)]
    body_html: str | None = None
    body_text: str | None = None


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


class Template(BaseModel):
    ref: TemplateRef
    context_schema: dict[str, Any]


class TemplatePreview(BaseModel):
    ref: TemplateRef
    message_content: dict[str, Any]
