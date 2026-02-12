from typing import Annotated, Any

from pydantic import BaseModel, Field

from models_library.groups import GroupID

from ..api_schemas_webserver._base import InputSchema, OutputSchema
from ..notifications import ChannelType, TemplateName


class EmailMessageContentBody(InputSchema):
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


type MessageContentBody = EmailMessageContentBody


class EmailMessageContentGet(OutputSchema):
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


type MessageContentGet = EmailMessageContentGet


class SearchTemplatesQueryParams(BaseModel):
    channel: ChannelType | None = None
    template_name: str | None = None


class TemplateRefBody(InputSchema):
    channel: ChannelType
    template_name: TemplateName


class TemplateRefGet(OutputSchema):
    channel: ChannelType
    template_name: TemplateName


class TemplateGet(OutputSchema):
    ref: TemplateRefGet
    context_schema: dict[str, Any]


class TemplatePreviewBody(InputSchema):
    ref: TemplateRefBody
    context: dict[str, Any]


class TemplatePreviewGet(OutputSchema):
    ref: TemplateRefGet
    content: MessageContentGet


class TemplateMessageBody(InputSchema):
    ref: TemplateRefBody
    group_ids: list[GroupID]
    context: dict[str, Any]


class MessageBody(InputSchema):
    channel: ChannelType
    group_ids: list[GroupID] | None = None
    content: MessageContentBody
