from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ChannelType(StrEnum):
    email = "email"


type TemplateName = Annotated[str, Field(min_length=1)]


class TemplateRef(BaseModel):
    channel: ChannelType
    template_name: TemplateName

    model_config = ConfigDict(frozen=True)


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


class EmailEnvelope(NotificationsMessage):
    channel: ChannelType = ChannelType.email
    from_: Annotated[EmailContact, Field(alias="from")]
    to: list[EmailContact]


class EmailMessage(EmailEnvelope):
    channel: ChannelType = ChannelType.email
    content: EmailMessageContent
