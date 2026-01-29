from typing import Any

from pydantic import BaseModel, Field

from models_library.groups import GroupID

from ..api_schemas_webserver._base import InputSchema, OutputSchema
from ..notifications import ChannelType, TemplateName


class NotificationsEmailContentBody(InputSchema):
    subject: str = Field(
        ...,
        min_length=1,
        max_length=998,
        description="Email subject line (RFC 2822: max header line length)",
    )
    body_html: str = Field(
        ...,
        min_length=1,
        max_length=1_048_576,
        description="HTML email body (1 MB limit per RFC 5321 SMTP practical limits)",
    )
    body_text: str = Field(
        ...,
        min_length=1,
        max_length=1_048_576,
        description="Plain text email body (1 MB limit per RFC 5321 SMTP practical limits)",
    )


type NotificationsContentBody = NotificationsEmailContentBody


class NotificationsEmailContentGet(OutputSchema):
    subject: str = Field(
        ...,
        min_length=1,
        max_length=998,
        description="Email subject line (RFC 2822: max header line length)",
    )
    body_html: str = Field(
        ...,
        min_length=1,
        max_length=1_048_576,
        description="HTML email body (1 MB limit per RFC 5321 SMTP practical limits)",
    )
    body_text: str = Field(
        ...,
        min_length=1,
        max_length=1_048_576,
        description="Plain text email body (1 MB limit per RFC 5321 SMTP practical limits)",
    )


type NotificationsContentGet = NotificationsEmailContentGet


class SearchTemplatesQueryParams(BaseModel):
    channel: ChannelType | None = None
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
