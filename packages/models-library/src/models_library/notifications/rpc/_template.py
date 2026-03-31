from typing import Any

from pydantic import BaseModel, ConfigDict

from .. import Channel, TemplateName


class TemplateRef(BaseModel):
    channel: Channel
    template_name: TemplateName

    model_config = ConfigDict(
        frozen=True,
    )


class SearchTemplatesResponse(BaseModel):
    ref: TemplateRef
    context_schema: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class PreviewTemplateRequest(BaseModel):
    ref: TemplateRef
    context: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class PreviewTemplateResponse(BaseModel):
    ref: TemplateRef
    message_content: dict[str, Any]

    model_config = ConfigDict(frozen=True)
