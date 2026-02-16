from typing import Any

from pydantic import BaseModel, ConfigDict

from ...notifications import ChannelType, TemplateName


class NotificationsTemplateRefRpc(BaseModel):
    channel: ChannelType
    template_name: TemplateName

    model_config = ConfigDict(frozen=True)


class NotificationsTemplateRpcResponse(BaseModel):
    ref: NotificationsTemplateRefRpc
    context_schema: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class NotificationsTemplatePreviewRpcRequest(BaseModel):
    ref: NotificationsTemplateRefRpc
    context: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class NotificationsSendFromTemplateRpcRequest(BaseModel):
    ref: NotificationsTemplateRefRpc
    context: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class NotificationsTemplatePreviewRpcResponse(BaseModel):
    ref: NotificationsTemplateRefRpc
    content: dict[str, Any]

    model_config = ConfigDict(frozen=True)
