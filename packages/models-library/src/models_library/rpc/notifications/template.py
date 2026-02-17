from typing import Any

from pydantic import BaseModel, ConfigDict

from ...notifications import ChannelType, TemplateName


class TemplateRefRpc(BaseModel):
    channel: ChannelType
    template_name: TemplateName

    model_config = ConfigDict(frozen=True)


class TemplateRpcResponse(BaseModel):
    ref: TemplateRefRpc
    context_schema: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class TemplatePreviewRpcRequest(BaseModel):
    ref: TemplateRefRpc
    context: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class TemplatePreviewRpcResponse(BaseModel):
    ref: TemplateRefRpc
    message_content: dict[str, Any]

    model_config = ConfigDict(frozen=True)
