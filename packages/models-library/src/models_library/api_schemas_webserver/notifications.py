from typing import Annotated, Any

from pydantic import BaseModel, Field

from models_library.groups import GroupID

from ..api_schemas_webserver._base import InputSchema, OutputSchema
from ..notifications import ChannelType, TemplateName


class NotificationsEmailContentBody(InputSchema):
    subject: Annotated[
        str,
        Field(
            ...,
            max_length=998,
            description="Email subject line (RFC 2822: max header line length)",
        ),
    ]
    body_html: Annotated[
        str,
        Field(
            ...,
            max_length=1_048_576,
            description="HTML email body (1 MB limit per RFC 5321 SMTP practical limits)",
        ),
    ]
    body_text: Annotated[
        str,
        Field(
            ...,
            max_length=1_048_576,
            description="Plain text email body (1 MB limit per RFC 5321 SMTP practical limits)",
        ),
    ]


type NotificationsContentBody = NotificationsEmailContentBody


class NotificationsEmailContentGet(OutputSchema):
    subject: Annotated[
        str,
        Field(
            ...,
            max_length=998,
            description="Email subject line (RFC 2822: max header line length)",
        ),
    ]
    body_html: Annotated[
        str,
        Field(
            ...,
            max_length=1_048_576,
            description="HTML email body (1 MB limit per RFC 5321 SMTP practical limits)",
        ),
    ]
    body_text: Annotated[
        str,
        Field(
            ...,
            max_length=1_048_576,
            description="Plain text email body (1 MB limit per RFC 5321 SMTP practical limits)",
        ),
    ]


type NotificationsContentGet = NotificationsEmailContentGet


class SearchTemplatesQueryParams(BaseModel):
    channel: ChannelType | None = None
    template_name: str | None = None


class NotificationsTemplateRefBody(InputSchema):
    channel: ChannelType
    template_name: TemplateName


class NotificationsTemplateRefGet(OutputSchema):
    channel: ChannelType
    template_name: TemplateName


class NotificationsTemplateGet(OutputSchema):
    ref: NotificationsTemplateRefGet
    context_schema: dict[str, Any]


class NotificationsTemplatePreviewBody(InputSchema):
    ref: NotificationsTemplateRefBody
    context: dict[str, Any]


class NotificationsTemplatePreviewGet(OutputSchema):
    ref: NotificationsTemplateRefGet
    content: NotificationsContentGet


class NotificationsTemplateMessageBody(InputSchema):
    ref: NotificationsTemplateRefBody
    recipients: list[GroupID]
    context: dict[str, Any]


class NotificationsMessageBody(InputSchema):
    channel: ChannelType
    recipients: list[GroupID]
    content: NotificationsContentBody
