from typing import Any

from pydantic import BaseModel, ConfigDict

from .. import TemplateRef


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
