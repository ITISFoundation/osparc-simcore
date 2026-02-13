from typing import Annotated, Any, Self

from pydantic import BaseModel, Field, model_validator

from models_library.groups import GroupID

from ..api_schemas_webserver._base import InputSchema, OutputSchema
from ..notifications import ChannelType, TemplateName

#
# Email Message
#


class _EmailMessageContentMixin(BaseModel):
    subject: Annotated[
        str,
        Field(
            ...,
            max_length=998,
            description="Email subject line (RFC 2822: max header line length)",
        ),
    ]
    body_html: str | None = None
    body_text: str | None = None

    @model_validator(mode="after")
    def _require_at_least_one_format(self) -> Self:
        if self.body_html is None and self.body_text is None:
            msg = "At least one of 'body_html' or 'body_text' is required"
            raise ValueError(msg)
        return self


class EmailMessageContent(_EmailMessageContentMixin, InputSchema): ...


class EmailMessageContentGet(_EmailMessageContentMixin, OutputSchema): ...


# Message

type MessageContent = EmailMessageContent  # | OtherMessageContent for other channels
type MessageContentGet = EmailMessageContentGet  # | OtherMessageContentGet for other channels


#
# Template
#


class SearchTemplatesQueryParams(BaseModel):
    """Search for templates based on channel and/or template name."""

    channel: ChannelType | None = None
    template_name: str | None = None


class _TemplateRefMixin(BaseModel):
    channel: ChannelType
    template_name: TemplateName


class TemplateRef(_TemplateRefMixin, InputSchema): ...


class TemplateRefGet(_TemplateRefMixin, OutputSchema): ...


class TemplateGet(OutputSchema):
    ref: TemplateRefGet
    context_schema: dict[str, Any]


class TemplatePreviewBody(InputSchema):
    ref: TemplateRef
    context: dict[str, Any]


class TemplatePreviewGet(OutputSchema):
    ref: TemplateRefGet
    message_content: MessageContentGet


class TemplateMessageBody(InputSchema):
    ref: TemplateRef
    group_ids: list[GroupID]
    context: dict[str, Any]


class MessageBody(InputSchema):
    channel: ChannelType
    group_ids: list[GroupID] | None = None
    content: MessageContent
