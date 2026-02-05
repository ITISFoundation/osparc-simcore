from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, EmailStr, Field


class ChannelType(StrEnum):
    email = "email"


type TemplateName = Annotated[str, Field(min_length=1)]


class TemplateRef(BaseModel):
    channel: ChannelType
    template_name: TemplateName


class NotificationsEmailAddress(BaseModel):
    display_name: str
    addr_spec: EmailStr


class NotificationsEmailMessageContent(BaseModel):
    subject: str
    body_html: str
    body_text: str


type NotificationsMessageContent = (
    NotificationsEmailMessageContent
    # add here other channel contents (e.g. | SMSNotificationsContent)
)


class NotificationsMessage(BaseModel):
    channel: ChannelType


class NotificationsEmailMessage(NotificationsMessage):
    channel: ChannelType = ChannelType.email
    from_: Annotated[NotificationsEmailAddress, Field(alias="from")]
    to: list[NotificationsEmailAddress]
    content: NotificationsEmailMessageContent


class NotificationsTemplatePreview(BaseModel):
    ref: TemplateRef
    content: dict[str, Any]
