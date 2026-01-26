from typing import Any

from pydantic import BaseModel

from models_library.groups import GroupID

from ..api_schemas_webserver._base import InputSchema, OutputSchema
from ..notifications import ChannelType, TemplateName


class NotificationsEmailContentBody(InputSchema):
    subject: str
    body_html: str
    body_text: str


type NotificationsContentBody = NotificationsEmailContentBody


class NotificationsEmailContentGet(OutputSchema):
    subject: str
    body_html: str
    body_text: str


type NotificationsContentGet = NotificationsEmailContentGet


class SearchTemplatesQueryParams(BaseModel):
    # NOTE: str because we support wildcards
    channel: str | None = None
    template_name: str | None = None


class NotificationsTemplateRefGet(OutputSchema):
    channel: ChannelType
    template_name: TemplateName


class NotificationsTemplateGet(OutputSchema):
    ref: NotificationsTemplateRefGet
    context_schema: dict[str, Any]


class NotificationsTemplatePreviewBody(InputSchema):
    ref: NotificationsTemplateRefGet
    context: dict[str, Any]


class NotificationsTemplatePreviewGet(OutputSchema):
    ref: NotificationsTemplateRefGet
    content: NotificationsContentGet


class NotificationsTemplateMessageBody(InputSchema):
    ref: NotificationsTemplateRefGet
    recipients: list[GroupID]
    context: dict[str, Any]


class NotificationsMessageBody(InputSchema):
    channel: ChannelType
    recipients: list[GroupID]
    content: NotificationsContentBody
