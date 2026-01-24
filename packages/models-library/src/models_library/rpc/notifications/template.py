from typing import Any

from pydantic import BaseModel

from ...notifications import ChannelType, TemplateName


class NotificationsTemplateRefRpc(BaseModel):
    channel: ChannelType
    template_name: TemplateName


class NotificationsTemplateRpcResponse(BaseModel):
    ref: NotificationsTemplateRefRpc
    context_schema: dict[str, Any]


class NotificationsTemplatePreviewRpcRequest(BaseModel):
    ref: NotificationsTemplateRefRpc
    context: dict[str, Any]


class NotificationsTemplatePreviewRpcResponse(BaseModel):
    ref: NotificationsTemplateRefRpc
    content: dict[str, Any]
