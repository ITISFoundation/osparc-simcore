from typing import Annotated, Any, Self

from pydantic import BaseModel, Field, model_validator

from models_library.groups import GroupID

from ..api_schemas_webserver._base import InputSchema, OutputSchema
from ..notifications import ChannelType, TemplateName

#
# Email Message
#


class _EmailMessageContentBodyMixin(BaseModel):
    html: str | None = None
    text: str | None = None

    @model_validator(mode="after")
    def _require_at_least_one_format(self) -> Self:
        if self.html is None and self.text is None:
            msg = "At least one of 'html' or 'text' is required"
            raise ValueError(msg)
        return self


class EmailMessageContentBody(_EmailMessageContentBodyMixin, InputSchema): ...


class EmailMessageContentBodyGet(_EmailMessageContentBodyMixin, OutputSchema): ...


class _EmailMessageContentMixin(BaseModel):
    subject: Annotated[
        str,
        Field(
            ...,
            max_length=998,
            description="Email subject line (RFC 2822: max header line length)",
        ),
    ]


class EmailMessageContent(_EmailMessageContentMixin, InputSchema):
    body: EmailMessageContentBody


class EmailMessageContentGet(_EmailMessageContentMixin, OutputSchema):
    body: EmailMessageContentBodyGet


# Message

type MessageContent = EmailMessageContent  # | OtherMessageContent for other channels
type MessageContentGet = EmailMessageContentGet  # | OtherMessageContentGet for other channels


#
# Template
#


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
    content: MessageContent
